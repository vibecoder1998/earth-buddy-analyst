#!/usr/bin/env bash
# Run Earth Buddy's model on one EC2 GPU host: Ollama on 127.0.0.1, Caddy in front with TLS and a bearer key.
# Every resource carries the tag Name=earthbuddy-llm. The key and model live only in the instance's user-data.
set -euo pipefail

REGION=${REGION:-us-east-1}
INSTANCE_TYPE=${INSTANCE_TYPE:-g4dn.xlarge}
MODEL=${MODEL:-qwen3:8b}
DISK_GB=${DISK_GB:-60}
NAME=earthbuddy-llm
AMI_PARAM=/aws/service/deeplearning/ami/x86_64/base-oss-nvidia-driver-gpu-ubuntu-22.04/latest/ami-id
TAGS="Tags=[{Key=Name,Value=$NAME}]"
export AWS_PAGER=""

die() { echo "llm-host: $*" >&2; exit 1; }

# `|| return` because bash drops errexit inside $(...), which would hide an aws failure.
ec2() { local v; v=$(aws ec2 "$@" --region "$REGION" --output text) || return; [ -z "$v" ] || [ "$v" = None ] || echo "$v"; }

sg_id() { ec2 describe-security-groups --filters "Name=tag:Name,Values=$NAME" --query 'SecurityGroups[0].GroupId'; }
eip() { ec2 describe-addresses --filters "Name=tag:Name,Values=$NAME" --query 'Addresses[0].[AllocationId,PublicIp,InstanceId]'; }
instance() {
  ec2 describe-instances --filters "Name=tag:Name,Values=$NAME" "Name=instance-state-name,Values=${1:-pending,running,stopping,stopped}" \
    --query 'Reservations[].Instances[] | [0].[InstanceId,State.Name]'
}

find_instance() {
  local x; x=$(instance)
  read -r id state <<<"$x"
  [ -n "$id" ] || die "no instance tagged $NAME in $REGION; run: $0 up"
}

load() {
  local u
  find_instance
  u=$(ec2 describe-instance-attribute --instance-id "$id" --attribute userData --query UserData.Value | base64 --decode)
  HOST=$(sed -n 's/^HOST=//p' <<<"$u")
  KEY=$(sed -n 's/^KEY=//p' <<<"$u")
  UMODEL=$(sed -n 's/^MODEL=//p' <<<"$u")
}

user_data() { # ip host key
  printf '#!/bin/bash\nIP=%s\nHOST=%s\nKEY=%s\nMODEL=%s\n' "$1" "$2" "$3" "$MODEL"
  cat <<'EOF'
set -euxo pipefail
export HOME=/root DEBIAN_FRONTEND=noninteractive
APT="apt-get -y -o DPkg::Lock::Timeout=600"

# Associating the Elastic IP swaps the public address and drops open downloads, so wait for it first.
tok() { curl -sf -X PUT http://169.254.169.254/latest/api/token -H 'X-aws-ec2-metadata-token-ttl-seconds: 60'; }
until [ "$(curl -sf -H "X-aws-ec2-metadata-token: $(tok)" http://169.254.169.254/latest/meta-data/public-ipv4)" = "$IP" ]; do sleep 5; done

curl -fsSL https://ollama.com/install.sh | sh
mkdir -p /etc/systemd/system/ollama.service.d
printf '[Service]\nEnvironment=OLLAMA_KEEP_ALIVE=-1\n' >/etc/systemd/system/ollama.service.d/earthbuddy.conf
systemctl daemon-reload
systemctl restart ollama
until ollama list >/dev/null 2>&1; do sleep 2; done
ollama pull "$MODEL"
ollama run "$MODEL" hi >/dev/null

$APT update
$APT install debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf https://dl.cloudsmith.io/public/caddy/stable/gpg.key | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt >/etc/apt/sources.list.d/caddy-stable.list
chmod o+r /usr/share/keyrings/caddy-stable-archive-keyring.gpg /etc/apt/sources.list.d/caddy-stable.list
$APT update
$APT install caddy

# Ollama rejects a non-local Host header while bound to loopback.
cat >/etc/caddy/Caddyfile <<CADDY
$HOST {
	@authed header Authorization "Bearer $KEY"
	handle @authed {
		reverse_proxy 127.0.0.1:11434 {
			header_up Host 127.0.0.1:11434
		}
	}
	handle {
		respond 401
	}
}
CADDY
systemctl reload caddy
EOF
}

cmd_up() {
  case $MODEL in '' | *[!A-Za-z0-9._:/-]*) die "MODEL has characters user-data cannot carry: $MODEL" ;; esac

  sg=$(sg_id)
  if [ -z "$sg" ]; then
    vpc=$(ec2 describe-vpcs --filters Name=is-default,Values=true --query 'Vpcs[0].VpcId')
    [ -n "$vpc" ] || die "no default VPC in $REGION"
    sg=$(ec2 create-security-group --group-name "$NAME" --description "Earth Buddy LLM host" --vpc-id "$vpc" \
      --tag-specifications "ResourceType=security-group,$TAGS" --query GroupId)
  fi
  for port in 80 443; do
    out=$(aws ec2 authorize-security-group-ingress --region "$REGION" --group-id "$sg" --protocol tcp --port "$port" --cidr 0.0.0.0/0 2>&1) ||
      case $out in *InvalidPermission.Duplicate*) ;; *) die "$out" ;; esac
  done

  e=$(eip)
  if [ -z "$e" ]; then
    e=$(ec2 allocate-address --domain vpc --tag-specifications "ResourceType=elastic-ip,$TAGS" --query '[AllocationId,PublicIp]')
  fi
  read -r alloc ip assoc <<<"$e"
  host=${ip//./-}.sslip.io

  x=$(instance)
  read -r id state <<<"$x"
  if [ -z "$id" ]; then
    ami=$(aws ssm get-parameter --region "$REGION" --name "$AMI_PARAM" --query Parameter.Value --output text)
    root=$(ec2 describe-images --image-ids "$ami" --query 'Images[0].RootDeviceName')
    ud_file=$(mktemp)
    trap 'rm -f "$ud_file"' EXIT
    user_data "$ip" "$host" "$(openssl rand -hex 32)" >"$ud_file"
    id=$(ec2 run-instances --image-id "$ami" --instance-type "$INSTANCE_TYPE" --security-group-ids "$sg" \
      --user-data "file://$ud_file" --metadata-options HttpTokens=required,HttpEndpoint=enabled \
      --block-device-mappings "DeviceName=$root,Ebs={VolumeSize=$DISK_GB,VolumeType=gp3,DeleteOnTermination=true}" \
      --tag-specifications "ResourceType=instance,$TAGS" "ResourceType=volume,$TAGS" --query 'Instances[0].InstanceId')
    echo "launched $id; first boot installs and pulls $MODEL, so give it ~10 minutes before: $0 check" >&2
  else
    start_existing
  fi
  ec2 wait instance-running --instance-ids "$id"
  [ "$assoc" = "$id" ] || ec2 associate-address --instance-id "$id" --allocation-id "$alloc" >/dev/null

  load
  [ "$HOST" = "$host" ] || die "instance $id was built for $HOST but the Elastic IP is $ip; run: $0 down && $0 up"
  cmd_env
}

start_existing() {
  if [ "$state" = stopping ]; then ec2 wait instance-stopped --instance-ids "$id"; fi
  if [ "$state" = stopping ] || [ "$state" = stopped ]; then ec2 start-instances --instance-ids "$id" >/dev/null; fi
}

cmd_env() {
  load
  printf 'EB_LLM_URL=https://%s/v1\nEB_MODEL=%s\nEB_LLM_KEY=%s\n' "$HOST" "$UMODEL" "$KEY"
}

cmd_check() {
  load
  base=https://$HOST/v1
  body=$(mktemp)
  trap 'rm -f "$body"' EXIT
  get() { curl -sS -m 20 -o "$body" -w '%{http_code}' "$@" "$base/models" || die "cannot reach $base (still booting, or TLS not issued yet)"; }

  code=$(get)
  [ "$code" = 401 ] || die "GET /v1/models without key: want 401, got $code"
  code=$(get -H "Authorization: Bearer $KEY")
  [ "$code" = 200 ] || die "GET /v1/models with key: want 200, got $code"
  python3 - "$body" "$UMODEL" <<'PY' 2>/dev/null || die "$UMODEL is not listed in /v1/models (still pulling?): $(cat "$body")"
import json, sys
sys.exit(sys.argv[2] not in [m["id"] for m in json.load(open(sys.argv[1]))["data"]])
PY

  schema='{"type":"object","properties":{"answer":{"type":"string"}},"required":["answer"],"additionalProperties":false}'
  req='{"model":"'$UMODEL'","temperature":0,"messages":[{"role":"user","content":"Answer with the word ok."}],'
  req=$req'"response_format":{"type":"json_schema","json_schema":{"name":"reply","strict":true,"schema":'$schema'}}}'
  out=$(curl -sS -m 300 -o "$body" -w '%{http_code} %{time_total}' -H "Authorization: Bearer $KEY" \
    -H 'Content-Type: application/json' -d "$req" "$base/chat/completions") || die "POST /v1/chat/completions failed"
  read -r code secs <<<"$out"
  [ "$code" = 200 ] || die "POST /v1/chat/completions: want 200, got $code: $(cat "$body")"
  python3 - "$body" <<'PY' 2>/dev/null || die "chat reply broke the json_schema contract: $(cat "$body")"
import json, sys
choice = json.load(open(sys.argv[1]))["choices"][0]
assert choice["finish_reason"] == "stop", choice["finish_reason"]
assert isinstance(json.loads(choice["message"]["content"])["answer"], str)
PY
  echo "ok: 401 without key, $UMODEL listed, json_schema chat took ${secs}s"
}

cmd_stop() {
  find_instance
  ec2 stop-instances --instance-ids "$id" >/dev/null
  ec2 wait instance-stopped --instance-ids "$id"
  echo "stopped $id"
}

cmd_start() {
  find_instance
  start_existing
  ec2 wait instance-running --instance-ids "$id"
  echo "running $id"
}

cmd_down() {
  x=$(instance pending,running,stopping,stopped,shutting-down)
  read -r id state <<<"$x"
  if [ -n "$id" ]; then
    ec2 terminate-instances --instance-ids "$id" >/dev/null
    ec2 wait instance-terminated --instance-ids "$id"
    echo "terminated $id"
  fi
  e=$(eip)
  read -r alloc ip assoc <<<"$e"
  if [ -n "$alloc" ]; then
    ec2 release-address --allocation-id "$alloc" >/dev/null
    echo "released $ip"
  fi
  sg=$(sg_id)
  if [ -n "$sg" ]; then
    # A terminated instance's network interface can hold the group for a little while.
    n=0
    until ec2 delete-security-group --group-id "$sg" >/dev/null 2>&1; do
      n=$((n + 1))
      [ "$n" -lt 24 ] || die "could not delete $sg"
      sleep 5
    done
    echo "deleted $sg"
  fi
}

case ${1:-} in
  up | env | check | stop | start | down) "cmd_$1" ;;
  *)
    echo "usage: $0 up|env|check|stop|start|down   (env: REGION INSTANCE_TYPE MODEL DISK_GB AWS_PROFILE)" >&2
    exit 2
    ;;
esac

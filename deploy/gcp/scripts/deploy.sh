#!/usr/bin/env bash
# deploy.sh — Deploy Django backend to GCP VM with PostgreSQL container
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TERRAFORM_DIR="$SCRIPT_DIR/../terraform"
COMPOSE_DIR="$SCRIPT_DIR/../compose"
PROJECT_ROOT="$SCRIPT_DIR/../../.."

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[deploy]${NC} $*"; }
warn() { echo -e "${YELLOW}[warn]${NC} $*"; }
die() { echo -e "${RED}[error]${NC} $*" >&2; exit 1; }

# --- 1. Provision VM with Terraform ---
provision_vm() {
    log "Provisioning GCP VM with Terraform..."
    cd "$TERRAFORM_DIR"

    terraform init -input=false
    terraform apply -auto-approve -input=false

    # Save outputs
    EXTERNAL_IP=$(terraform output -raw instance_external_ip)
    INSTANCE_NAME=$(terraform output -raw instance_name)
    ZONE=$(terraform output -raw instance_zone)

    log "VM provisioned: $EXTERNAL_IP ($INSTANCE_NAME in $ZONE)"
    cd "$SCRIPT_DIR"
}

# --- 2. Wait for VM to be ready ---
wait_for_vm() {
    local ip="$1"
    log "Waiting for VM to be ready..."
    for i in $(seq 1 30); do
        if gcloud compute ssh ubuntu@"$ip" --zone="$ZONE" --command="echo ready" 2>/dev/null; then
            log "VM is ready"
            return 0
        fi
        sleep 10
    done
    die "VM did not become ready in 5 minutes"
}

# --- 3. Copy source code to VM ---
copy_source() {
    local ip="$1"
    log "Copying source code to VM..."

    # Create a tarball of the project (excluding unnecessary dirs)
    tar czf /tmp/ag-deploy.tar.gz \
        --exclude='.git' \
        --exclude='node_modules' \
        --exclude='__pycache__' \
        --exclude='*.pyc' \
        --exclude='.env' \
        --exclude='.env.local' \
        --exclude='deploy/gcp/terraform/.terraform' \
        -C "$PROJECT_ROOT" .

    # Upload tarball
    gcloud compute scp /tmp/ag-deploy.tar.gz ubuntu@"$ip":/tmp/ag-deploy.tar.gz --zone="$ZONE"

    # Extract on VM
    gcloud compute ssh ubuntu@"$ip" --zone="$ZONE" --command="
        sudo rm -rf /opt/affordable-gadgets/app
        sudo mkdir -p /opt/affordable-gadgets/app
        sudo tar xzf /tmp/ag-deploy.tar.gz -C /opt/affordable-gadgets/app
        sudo chown -R ubuntu:ubuntu /opt/affordable-gadgets/app
        rm /tmp/ag-deploy.tar.gz
    "

    log "Source code copied"
}

# --- 4. Copy environment file ---
copy_env() {
    local ip="$1"
    local env_file="${2:-$SCRIPT_DIR/../env/api.env}"

    if [ ! -f "$env_file" ]; then
        die "Environment file not found: $env_file\nCreate it from api.env.example"
    fi

    log "Copying environment file..."
    gcloud compute scp "$env_file" ubuntu@"$ip":/opt/affordable-gadgets/api.env --zone="$ZONE"
    gcloud compute ssh ubuntu@"$ip" --zone="$ZONE" --command="
        sudo chown ubuntu:ubuntu /opt/affordable-gadgets/api.env
        sudo chmod 600 /opt/affordable-gadgets/api.env
    "
    log "Environment file copied"
}

# --- 5. Copy Docker Compose file ---
copy_compose() {
    local ip="$1"
    log "Copying Docker Compose file..."
    gcloud compute scp "$COMPOSE_DIR/docker-compose.prod.yml" ubuntu@"$ip":/opt/affordable-gadgets/docker-compose.yml --zone="$ZONE"
    log "Docker Compose file copied"
}

# --- 6. Deploy and start services ---
deploy_services() {
    local ip="$1"
    log "Building and starting services..."

    gcloud compute ssh ubuntu@"$ip" --zone="$ZONE" --command="
        cd /opt/affordable-gadgets/app

        # Build Django image
        docker compose -f /opt/affordable-gadgets/docker-compose.yml build web

        # Stop existing services
        docker compose -f /opt/affordable-gadgets/docker-compose.yml down

        # Start PostgreSQL first
        docker compose -f /opt/affordable-gadgets/docker-compose.yml up -d db

        # Wait for PostgreSQL to be healthy
        echo 'Waiting for PostgreSQL...'
        for i in \$(seq 1 30); do
            if docker exec ag-postgres pg_isready -U affordable -d affordable_gadgets 2>/dev/null; then
                echo 'PostgreSQL is ready'
                break
            fi
            sleep 2
        done

        # Restore dump if pgdata is empty
        if [ ! -f /opt/affordable-gadgets/pgdata/.dump_restored ]; then
            echo 'Restoring database dump...'
            # Upload dump first (done outside this script)
            if [ -f /tmp/affordable_gadgets.dump ]; then
                docker exec -i ag-postgres pg_restore -U affordable -d affordable_gadgets --no-owner --no-acl < /tmp/affordable_gadgets.dump || true
                touch /opt/affordable-gadgets/pgdata/.dump_restored
                echo 'Dump restored'
            fi
        fi

        # Start Django
        docker compose -f /opt/affordable-gadgets/docker-compose.yml up -d web

        # Show status
        docker compose -f /opt/affordable-gadgets/docker-compose.yml ps
    "

    log "Services started"
}

# --- Main ---
main() {
    local action="${1:-deploy}"

    case "$action" in
        provision)
            provision_vm
            ;;
        deploy)
            # Check if VM exists
            if [ -f "$TERRAFORM_DIR/terraform.tfstate" ]; then
                EXTERNAL_IP=$(cd "$TERRAFORM_DIR" && terraform output -raw instance_external_ip 2>/dev/null || true)
                ZONE=$(cd "$TERRAFORM_DIR" && terraform output -raw instance_zone 2>/dev/null || true)
            fi

            if [ -z "${EXTERNAL_IP:-}" ]; then
                provision_vm
            fi

            log "Deploying to $EXTERNAL_IP..."
            wait_for_vm "$EXTERNAL_IP"
            copy_source "$EXTERNAL_IP"
            copy_env "$EXTERNAL_IP"
            copy_compose "$EXTERNAL_IP"
            deploy_services "$EXTERNAL_IP"

            log "Deployment complete!"
            log "Django is running at http://$EXTERNAL_IP:8000"
            log "Health check: http://$EXTERNAL_IP:8000/health/"
            ;;
        destroy)
            log "Destroying VM..."
            cd "$TERRAFORM_DIR"
            terraform destroy -auto-approve
            log "VM destroyed"
            ;;
        status)
            if [ -f "$TERRAFORM_DIR/terraform.tfstate" ]; then
                cd "$TERRAFORM_DIR"
                terraform output
            else
                warn "No Terraform state found. Run: $0 provision"
            fi
            ;;
        *)
            echo "Usage: $0 {provision|deploy|destroy|status}"
            exit 1
            ;;
    esac
}

main "$@"

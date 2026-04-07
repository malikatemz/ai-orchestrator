#!/bin/bash

#############################################################################
# AI Orchestrator - Kubernetes Automated Deployment Script
#
# This script automates the deployment of AI Orchestrator to Kubernetes
# Prerequisites:
#  - kubectl configured and connected to K8s cluster
#  - Helm installed (for optional components)
#  - Docker image already pushed to registry
#
# Usage:
#   ./deploy-ai-orchestrator.sh [environment] [domain]
#
# Example:
#   ./deploy-ai-orchestrator.sh staging yourdomain.com
#   ./deploy-ai-orchestrator.sh prod yourdomain.com
#############################################################################

set -e

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
ENVIRONMENT="${1:-prod}"
DOMAIN="${2:-yourdomain.com}"
NAMESPACE="ai-orchestrator-${ENVIRONMENT}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Functions
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

success() {
    echo -e "${GREEN}✓ $1${NC}"
}

error() {
    echo -e "${RED}✗ $1${NC}"
    exit 1
}

warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

# Check prerequisites
check_prerequisites() {
    log "Checking prerequisites..."
    
    # Check kubectl
    if ! command -v kubectl &> /dev/null; then
        error "kubectl not found. Please install kubectl."
    fi
    success "kubectl is installed"
    
    # Check cluster connectivity
    if ! kubectl cluster-info &> /dev/null; then
        error "Cannot connect to Kubernetes cluster. Please configure kubectl."
    fi
    success "Connected to Kubernetes cluster"
    
    # Check manifest files exist
    if [ ! -d "${SCRIPT_DIR}/k8s" ]; then
        error "k8s directory not found. Please ensure you're in the repository root."
    fi
    success "Manifest files found"
}

# Create namespace
create_namespace() {
    log "Creating namespace: $NAMESPACE"
    
    kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -
    
    # Add labels
    kubectl label namespace "$NAMESPACE" \
        environment="${ENVIRONMENT}" \
        managed-by=ai-orchestrator \
        --overwrite
    
    success "Namespace created: $NAMESPACE"
}

# Create secrets
create_secrets() {
    log "Creating secrets..."
    
    # Generate secure values
    JWT_SECRET=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))' 2>/dev/null || openssl rand -base64 32)
    DB_PASSWORD=$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))' 2>/dev/null || openssl rand -base64 24)
    REDIS_PASSWORD=$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))' 2>/dev/null || openssl rand -base64 24)
    
    log "Generated secure credentials"
    
    # Create secret
    kubectl create secret generic ai-orchestrator-secrets \
        --from-literal=DATABASE_URL="postgresql://postgres:${DB_PASSWORD}@postgres-service:5432/ai_orchestrator" \
        --from-literal=REDIS_URL="redis://:${REDIS_PASSWORD}@redis-service:6379/0" \
        --from-literal=JWT_SECRET_KEY="${JWT_SECRET}" \
        --from-literal=CELERY_BROKER_URL="redis://:${REDIS_PASSWORD}@redis-service:6379/1" \
        --from-literal=CELERY_RESULT_BACKEND="redis://:${REDIS_PASSWORD}@redis-service:6379/2" \
        --from-literal=POSTGRES_USER="postgres" \
        --from-literal=POSTGRES_PASSWORD="${DB_PASSWORD}" \
        --from-literal=REDIS_AUTH_PASSWORD="${REDIS_PASSWORD}" \
        --namespace="$NAMESPACE" \
        --dry-run=client -o yaml | kubectl apply -f -
    
    success "Secrets created"
    
    # Store credentials for reference
    cat > "${SCRIPT_DIR}/.deployment-secrets-${ENVIRONMENT}" << EOF
# Database
DB_PASSWORD=${DB_PASSWORD}
DATABASE_URL=postgresql://postgres:${DB_PASSWORD}@postgres-service:5432/ai_orchestrator

# Redis
REDIS_PASSWORD=${REDIS_PASSWORD}
REDIS_URL=redis://:${REDIS_PASSWORD}@redis-service:6379/0

# JWT
JWT_SECRET_KEY=${JWT_SECRET}

# Store this file securely - it contains sensitive information
# Delete after verifying deployment
EOF
    
    warning "Credentials saved to .deployment-secrets-${ENVIRONMENT} (DELETE AFTER VERIFICATION)"
}

# Apply ConfigMap
apply_configmap() {
    log "Applying ConfigMap..."
    
    kubectl patch configmap ai-orchestrator-config \
        -p "{\"data\":{\"ENVIRONMENT\":\"${ENVIRONMENT}\"}}" \
        -n "$NAMESPACE" --type merge || \
    kubectl create configmap ai-orchestrator-config \
        --from-literal=ENVIRONMENT="${ENVIRONMENT}" \
        --from-literal=LOG_LEVEL="info" \
        --from-literal=API_TITLE="AI Orchestrator" \
        --from-literal=API_VERSION="1.0.0" \
        --from-literal=DATABASE_POOL_SIZE="20" \
        --from-literal=DATABASE_POOL_RECYCLE="3600" \
        --from-literal=REDIS_POOL_SIZE="10" \
        --from-literal=WORKER_CONCURRENCY="4" \
        --from-literal=WORKER_PREFETCH_MULTIPLIER="4" \
        --namespace="$NAMESPACE"
    
    success "ConfigMap applied"
}

# Deploy infrastructure
deploy_infrastructure() {
    log "Deploying infrastructure components..."
    
    # PVCs
    log "Creating PersistentVolumeClaims..."
    kubectl apply -f "${SCRIPT_DIR}/k8s/day2-pvc.yaml" -n "$NAMESPACE"
    success "PVCs created"
    
    # Services
    log "Creating Services..."
    kubectl apply -f "${SCRIPT_DIR}/k8s/day2-service.yaml" -n "$NAMESPACE"
    success "Services created"
    
    # Network Policies
    log "Applying Network Policies..."
    kubectl apply -f "${SCRIPT_DIR}/k8s/day3-network-policy.yaml" -n "$NAMESPACE"
    success "Network policies applied"
}

# Deploy database
deploy_database() {
    log "Deploying PostgreSQL..."
    
    kubectl apply -f "${SCRIPT_DIR}/k8s/day4-postgres-statefulset.yaml" -n "$NAMESPACE"
    
    # Wait for database to be ready
    log "Waiting for PostgreSQL to be ready (this may take 1-2 minutes)..."
    kubectl wait --for=condition=ready pod postgres-0 \
        -n "$NAMESPACE" \
        --timeout=300s || error "PostgreSQL failed to start"
    
    success "PostgreSQL is ready"
    
    # Test connection
    log "Testing database connection..."
    kubectl exec postgres-0 -n "$NAMESPACE" -- \
        psql -U postgres -d ai_orchestrator -c "SELECT version();" > /dev/null || error "Database connection failed"
    
    success "Database connection verified"
}

# Deploy cache
deploy_cache() {
    log "Deploying Redis..."
    
    kubectl apply -f "${SCRIPT_DIR}/k8s/day4-redis-statefulset.yaml" -n "$NAMESPACE"
    
    # Wait for Redis to be ready
    log "Waiting for Redis to be ready..."
    kubectl wait --for=condition=ready pod redis-0 \
        -n "$NAMESPACE" \
        --timeout=300s || error "Redis failed to start"
    
    success "Redis is ready"
    
    # Test connection
    log "Testing Redis connection..."
    kubectl exec redis-0 -n "$NAMESPACE" -- redis-cli ping > /dev/null || error "Redis connection failed"
    
    success "Redis connection verified"
}

# Deploy application
deploy_application() {
    log "Deploying application components..."
    
    # API deployment
    log "Deploying API service..."
    kubectl apply -f "${SCRIPT_DIR}/k8s/day1-api-deployment.yaml" -n "$NAMESPACE"
    
    # Wait for API to be ready
    kubectl rollout status deployment/ai-orchestrator-api \
        -n "$NAMESPACE" \
        --timeout=300s || error "API deployment failed"
    
    success "API service deployed"
    
    # Worker deployment
    log "Deploying workers..."
    kubectl apply -f "${SCRIPT_DIR}/k8s/day1-worker-deployment.yaml" -n "$NAMESPACE"
    
    # Wait for workers to be ready
    kubectl rollout status deployment/ai-orchestrator-worker \
        -n "$NAMESPACE" \
        --timeout=300s || error "Worker deployment failed"
    
    success "Workers deployed"
}

# Deploy autoscaling
deploy_autoscaling() {
    log "Deploying autoscaling configuration..."
    
    # HPA
    kubectl apply -f "${SCRIPT_DIR}/k8s/day1-hpa-cpu.yaml" -n "$NAMESPACE"
    success "HPA deployed"
    
    # KEDA (optional, if installed)
    if kubectl get crd scaledobjects.keda.sh &> /dev/null; then
        kubectl apply -f "${SCRIPT_DIR}/k8s/day1-hpa-keda.yaml" -n "$NAMESPACE"
        success "KEDA deployed"
    else
        warning "KEDA not installed, skipping queue-based autoscaling"
    fi
}

# Deploy networking and ingress
deploy_networking() {
    log "Deploying networking components..."
    
    # Update domain in ingress manifest
    sed "s/yourdomain.com/${DOMAIN}/g" \
        "${SCRIPT_DIR}/k8s/day3-ingress.yaml" | \
        kubectl apply -n "$NAMESPACE" -f -
    
    success "Ingress deployed for domain: $DOMAIN"
}

# Deploy monitoring
deploy_monitoring() {
    log "Deploying monitoring components..."
    
    kubectl apply -f "${SCRIPT_DIR}/k8s/day3-prometheus-config.yaml" -n "$NAMESPACE"
    kubectl apply -f "${SCRIPT_DIR}/k8s/day3-monitoring-config.yaml" -n "$NAMESPACE"
    
    success "Monitoring deployed"
}

# Deploy backup
deploy_backup() {
    log "Deploying backup configuration..."
    
    kubectl apply -f "${SCRIPT_DIR}/k8s/day4-postgres-backup.yaml" -n "$NAMESPACE"
    
    success "Backup CronJob deployed"
}

# Verify deployment
verify_deployment() {
    log "Verifying deployment..."
    
    echo ""
    echo "=== Pod Status ==="
    kubectl get pods -n "$NAMESPACE"
    
    echo ""
    echo "=== Service Status ==="
    kubectl get svc -n "$NAMESPACE"
    
    echo ""
    echo "=== PVC Status ==="
    kubectl get pvc -n "$NAMESPACE"
    
    echo ""
    echo "=== Deployment Status ==="
    kubectl get deployments -n "$NAMESPACE"
    
    echo ""
    echo "=== Ingress Status ==="
    kubectl get ingress -n "$NAMESPACE"
    
    echo ""
    echo "=== HPA Status ==="
    kubectl get hpa -n "$NAMESPACE"
}

# Main deployment flow
main() {
    echo ""
    echo -e "${BLUE}════════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}   AI Orchestrator Kubernetes Deployment${NC}"
    echo -e "${BLUE}════════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo "Environment: $ENVIRONMENT"
    echo "Domain: $DOMAIN"
    echo "Namespace: $NAMESPACE"
    echo ""
    
    # Check prerequisites
    check_prerequisites
    
    echo ""
    log "Starting deployment..."
    
    # Create namespace
    create_namespace
    
    # Create secrets
    create_secrets
    
    # Apply ConfigMap
    apply_configmap
    
    # Deploy infrastructure
    deploy_infrastructure
    
    # Deploy database
    deploy_database
    
    # Deploy cache
    deploy_cache
    
    # Deploy application
    deploy_application
    
    # Deploy autoscaling
    deploy_autoscaling
    
    # Deploy networking
    deploy_networking
    
    # Deploy monitoring
    deploy_monitoring
    
    # Deploy backup
    deploy_backup
    
    # Verify deployment
    verify_deployment
    
    echo ""
    echo -e "${GREEN}════════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}   Deployment Completed Successfully!${NC}"
    echo -e "${GREEN}════════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Verify all pods are running:"
    echo "     kubectl get pods -n $NAMESPACE"
    echo ""
    echo "  2. Test API health:"
    echo "     kubectl port-forward svc/ai-orchestrator-api 8000:8000 -n $NAMESPACE &"
    echo "     curl http://localhost:8000/health"
    echo ""
    echo "  3. Check ingress status:"
    echo "     kubectl get ingress -n $NAMESPACE"
    echo ""
    echo "  4. View logs:"
    echo "     kubectl logs deployment/ai-orchestrator-api -n $NAMESPACE -f"
    echo ""
    echo "  5. Check monitoring:"
    echo "     kubectl port-forward svc/prometheus 9090:9090 -n $NAMESPACE &"
    echo "     Open http://localhost:9090"
    echo ""
    echo "Documentation:"
    echo "  - Deployment Guide: docs/K8S_DEPLOYMENT_GUIDE.md"
    echo "  - Operations Guide: docs/K8S_OPERATIONS_GUIDE.md"
    echo "  - Troubleshooting: docs/K8S_TROUBLESHOOTING_GUIDE.md"
    echo ""
}

# Run main function
main

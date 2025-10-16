# Report styles
export BOLD=$(tput bold)
export BLUE=$(tput setaf 4)
export GREEN=$(tput setaf 2)
export YELLOW=$(tput setaf 3)
export RED=$(tput setaf 1)
export RESET=$(tput sgr0)

# Logger function
log_info() {
  DT=`date "+%Y-%m-%d %H:%M:%S"`
  echo "${DT} :: ${BOLD}${BLUE}==> ${RESET}${BOLD}$1${RESET}"
}

# Set environment variables
export GITHUB_USER="hrithviks"
export GITHUB_TOKEN=
export CSB_API_AUTH_TOKEN="token-value-for-api-service"

# Postgres
export CSB_POSTGRES_HOST=
export CSB_POSTGRES_DB="csb_db"
export CSB_POSTGRES_PORT=2345
export CSB_POSTGRES_USER="CSB_API_USER"
export CSB_POSTGRES_PSWD="CSB_API_USER_PSWD"
export CSB_POSTGRES_MAX_CONN=5

# Redis
export CSB_REDIS_HOST=
export CSB_REDIS_PORT=2367
export CSB_REDIS_PSWD=
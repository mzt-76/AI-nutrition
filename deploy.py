#!/usr/bin/env python3
"""
deploy.py — Deploy the AI Nutrition stack.

Usage:
  python deploy.py --type local                          # Local (no Caddy)
  python deploy.py --type cloud                          # Cloud (with Caddy SSL)
  python deploy.py --down --type local                   # Stop services
  python deploy.py --type local --env-file ".env prod"   # Custom env file
"""
import argparse
import subprocess
import sys
import os


def run_command(cmd, cwd=None):
    print("Running:", " ".join(cmd))
    try:
        subprocess.run(cmd, cwd=cwd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Command failed with exit code {e.returncode}")
        sys.exit(1)


def validate_environment(deployment_type):
    required = ["docker-compose.yml", "Dockerfile", "frontend/Dockerfile",
                "src/RAG_Pipeline/Dockerfile"]
    if deployment_type == "cloud":
        required.extend(["docker-compose.caddy.yml", "Caddyfile"])

    for f in required:
        if not os.path.exists(f):
            print(f"Error: Required file '{f}' not found")
            sys.exit(1)


def deploy_stack(deployment_type, project_name, action="up", env_file=None):
    cmd = ["docker", "compose", "-p", project_name, "-f", "docker-compose.yml"]

    if env_file:
        cmd.extend(["--env-file", env_file])

    if deployment_type == "cloud":
        if not os.path.exists("docker-compose.caddy.yml"):
            print("Error: docker-compose.caddy.yml not found for cloud deployment")
            sys.exit(1)
        cmd.extend(["-f", "docker-compose.caddy.yml"])
        print("Cloud deployment: Including Caddy reverse proxy")
    else:
        print("Local deployment: Services on localhost:8001 (API) + localhost:8080 (frontend)")

    if action == "up":
        cmd.extend(["up", "-d", "--build"])
        print(f"Starting {deployment_type} deployment (project: {project_name})...")
    elif action == "down":
        cmd.extend(["down"])
        print(f"Stopping {deployment_type} deployment (project: {project_name})...")

    run_command(cmd)

    if action == "up":
        print(f"\n✅ {deployment_type.title()} deployment completed!")
        print(f"\nServices:")
        print(f"  Backend API:   http://localhost:8001")
        print(f"  Frontend:      http://localhost:8080")
        print(f"  RAG Pipeline:  running (no exposed port)")
        print(f"\nUseful commands:")
        print(f"  docker compose -p {project_name} logs -f          # Follow logs")
        print(f"  docker compose -p {project_name} ps               # Service status")
        print(f"  python deploy.py --down --type {deployment_type}  # Stop")

        if deployment_type == "cloud":
            print(f"\nCloud notes:")
            print(f"  - Configure AGENT_API_HOSTNAME and FRONTEND_HOSTNAME in .env")
            print(f"  - Caddy auto-provisions SSL certificates via Let's Encrypt")
    else:
        print(f"\n✅ {deployment_type.title()} deployment stopped.")


def main():
    parser = argparse.ArgumentParser(
        description='Deploy the AI Nutrition stack',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python deploy.py --type local
  python deploy.py --type cloud
  python deploy.py --down --type local
  python deploy.py --type local --env-file ".env prod"
        """
    )
    parser.add_argument('--type', choices=['local', 'cloud'], required=True,
                        help='local (no reverse proxy) or cloud (with Caddy SSL)')
    parser.add_argument('--project', default='ai-nutrition',
                        help='Docker Compose project name (default: ai-nutrition)')
    parser.add_argument('--down', action='store_true',
                        help='Stop and remove containers')
    parser.add_argument('--env-file', default=None,
                        help='Path to env file (e.g. ".env prod")')

    args = parser.parse_args()
    validate_environment(args.type)
    action = "down" if args.down else "up"
    deploy_stack(args.type, args.project, action, args.env_file)


if __name__ == "__main__":
    main()

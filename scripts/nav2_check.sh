#!/usr/bin/env bash
# Prove the exported map loads in a real ROS 2 Nav2 map_server (Docker).  Usage: scripts/nav2_check.sh out/office/scan/nav2
set -euo pipefail
MAPS="$(cd "${1:?nav2 dir with map.yaml}" && pwd)"; HERE="$(cd "$(dirname "$0")" && pwd)"
docker run --rm -v "$MAPS:/maps:ro" -v "$HERE/nav2_check_inner.sh:/run.sh:ro" public.ecr.aws/docker/library/ros:humble-ros-base bash /run.sh

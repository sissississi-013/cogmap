set -e
apt-get update -qq >/dev/null && apt-get install -y -qq ros-humble-nav2-map-server >/dev/null 2>&1
source /opt/ros/humble/setup.bash
cd /maps
echo "== map.yaml"; cat map.yaml
ros2 run nav2_map_server map_server --ros-args -p yaml_filename:=/maps/map.yaml -p use_sim_time:=false > /tmp/ms.log 2>&1 &
MS=$!
sleep 4
ros2 lifecycle set /map_server configure && ros2 lifecycle set /map_server activate
echo "== /map (first 12 lines of one message)"
timeout 25 ros2 topic echo /map --once --no-arr | head -20
echo "== map_server log"; tail -3 /tmp/ms.log
kill $MS || true

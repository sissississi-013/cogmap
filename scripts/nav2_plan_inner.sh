# Inside ros:humble-ros-base: load the CogMap map, bring up Nav2's planner_server with a static global costmap, ask it for a path.
set -e
source /opt/ros/humble/setup.bash
cd /maps
cat > /tmp/planner.yaml <<'YAML'
planner_server:
  ros__parameters:
    use_sim_time: false
    expected_planner_frequency: 1.0
    planner_plugins: ["GridBased"]
    GridBased:
      plugin: "nav2_navfn_planner/NavfnPlanner"
      tolerance: 0.6
      use_astar: true
      allow_unknown: true
global_costmap:
  global_costmap:
    ros__parameters:
      use_sim_time: false
      global_frame: map
      robot_base_frame: base_link
      robot_radius: 0.10
      resolution: 0.15
      track_unknown_space: true
      plugins: ["static_layer", "inflation_layer"]
      static_layer:
        plugin: "nav2_costmap_2d::StaticLayer"
        map_subscribe_transient_local: true
      inflation_layer:
        plugin: "nav2_costmap_2d::InflationLayer"
        inflation_radius: 0.2
        cost_scaling_factor: 3.0
      always_send_full_costmap: true
YAML
ros2 run nav2_map_server map_server --ros-args -p yaml_filename:=/maps/map.yaml > /tmp/ms.log 2>&1 &
ros2 run tf2_ros static_transform_publisher --frame-id map --child-frame-id base_link --x START_X --y START_Y > /dev/null 2>&1 &
ros2 run tf2_ros static_transform_publisher --frame-id map --child-frame-id odom > /dev/null 2>&1 &
ros2 run nav2_planner planner_server --ros-args --params-file /tmp/planner.yaml > /tmp/planner.log 2>&1 &
sleep 5
ros2 lifecycle set /map_server configure >/dev/null && ros2 lifecycle set /map_server activate >/dev/null
ros2 lifecycle set /planner_server configure >/dev/null && ros2 lifecycle set /planner_server activate >/dev/null
sleep 4
echo "== compute_path_to_pose from (START_X, START_Y) to (GOAL_X, GOAL_Y) [GOAL_NAME]"
timeout 40 ros2 action send_goal /compute_path_to_pose nav2_msgs/action/ComputePathToPose "{start: {header: {frame_id: map}, pose: {position: {x: START_X, y: START_Y}, orientation: {w: 1.0}}}, goal: {header: {frame_id: map}, pose: {position: {x: GOAL_X, y: GOAL_Y}, orientation: {w: 1.0}}}, use_start: true, planner_id: GridBased}" 2>&1 | grep -E "Goal accepted|poses:|planning_time|status|error_code" | head -8
echo "== path length (poses):"; timeout 40 ros2 action send_goal /compute_path_to_pose nav2_msgs/action/ComputePathToPose "{start: {header: {frame_id: map}, pose: {position: {x: START_X, y: START_Y}, orientation: {w: 1.0}}}, goal: {header: {frame_id: map}, pose: {position: {x: GOAL_X, y: GOAL_Y}, orientation: {w: 1.0}}}, use_start: true, planner_id: GridBased}" 2>&1 | grep -c "position:" || true
echo "== costmap info"; timeout 15 ros2 topic echo /global_costmap/costmap --once --no-arr 2>&1 | grep -E "width|height|resolution|x:|y:" | head -6
echo "== map_server log"; tail -3 /tmp/ms.log
echo "== planner log"; grep -vE "^\s*$" /tmp/planner.log | tail -12

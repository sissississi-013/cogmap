"""CogMap end-to-end runner.

  python run_demo.py --synthetic                 # synthetic apartment, full loop
  python run_demo.py --video footage/x.mp4       # real scan (Phase 4)
"""
import argparse, os, sys, json, time
from dotenv import load_dotenv


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--synthetic", action="store_true")
    ap.add_argument("--video", type=str, default=None)
    ap.add_argument("--rescan", type=str, default=None, help="second walkthrough video recorded after the space changed (real-world change round)")
    ap.add_argument("--out", type=str, default="out")
    ap.add_argument("--no-llm", action="store_true")
    ap.add_argument("--no-patrols", action="store_true")
    ap.add_argument("--no-explore", action="store_true")
    ap.add_argument("--n-tasks", type=int, default=16)
    ap.add_argument("--frames", type=int, default=48, help="keyframes sent to VGGT (48 fits an A10G; up to ~80)")
    ap.add_argument("--project", type=str, default="cogmap")
    ap.add_argument("--no-viz", action="store_true")
    args = ap.parse_args()
    load_dotenv()
    import weave
    weave.init(args.project)
    from cogmap.world import make_synthetic_apartment, default_tasks, BeliefMap, scripted_perturbations
    from cogmap.loop import CogMapLoop
    if args.video:
        from cogmap.scan.pipeline import scan_to_world
        world, belief, perturbations, tasks = scan_to_world(args.video, args.out, n_tasks=args.n_tasks, n_frames=args.frames)
        if args.rescan:
            from cogmap.scan.pipeline import rescan_perturbation
            perturbations = [rescan_perturbation(world, belief, args.rescan, args.out, n_frames=args.frames)] + perturbations[:1]
    else:
        world = make_synthetic_apartment()
        belief = BeliefMap.from_world(world, name="synthetic_apartment")
        tasks = default_tasks(world, args.n_tasks)
        perturbations = scripted_perturbations(world)
    loop = CogMapLoop(world, belief, tasks, out_dir=args.out, use_llm=not args.no_llm, use_patrols=not args.no_patrols,
                      use_explore=not args.no_explore)
    result = loop.run(perturbations)
    print("\n=== TIMELINE")
    for m in result["timeline"]:
        print(f"  {m['label']:<32} success={m['success_rate']:.2f} spl={m['spl']:.2f}")
    print("=== ROUNDS")
    for r in result["rounds"]:
        print(f"  round {r['round']}: steps_to_recover={r['steps_to_recover']} repairs={r['repairs']} final={r['final_success']:.2f}")
    print("leaderboard:", result["leaderboard"])
    if not args.no_viz:
        from cogmap.viz import render_all, log_images_to_weave
        render_all(args.out)
        print("weave images:", log_images_to_weave(args.out))


if __name__ == "__main__":
    main()

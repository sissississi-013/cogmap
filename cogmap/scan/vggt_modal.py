"""Modal app: run VGGT-1B on a directory of frames, return extrinsics/intrinsics/depth/point map/conf.

Run:  modal run vggt_modal.py --frames-dir frames --out out/vggt_out.npz
"""
import io, os, time, glob
import modal

app = modal.App("cogmap-vggt")

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("git", "libgl1", "libglib2.0-0")
    .pip_install(
        "torch==2.4.1", "torchvision==0.19.1",
        "numpy<2", "opencv-python-headless", "pillow", "huggingface_hub", "einops", "safetensors",
        "git+https://github.com/facebookresearch/vggt",
    )
)

weights_vol = modal.Volume.from_name("vggt-hf-cache", create_if_missing=True)
HF_CACHE = "/hf_cache"


@app.cls(
    image=image,
    gpu=os.environ.get("VGGT_GPU", "A10G"),
    timeout=1800,
    scaledown_window=600,
    volumes={HF_CACHE: weights_vol},
    env={"HF_HOME": HF_CACHE, "HF_HUB_ENABLE_HF_TRANSFER": "0"},
)
class VGGTRunner:
    @modal.enter()
    def load(self):
        import torch
        from vggt.models.vggt import VGGT
        t0 = time.time()
        self.device = "cuda"
        self.dtype = torch.bfloat16 if torch.cuda.get_device_capability()[0] >= 8 else torch.float16
        self.model = VGGT.from_pretrained("facebook/VGGT-1B").to(self.device).eval()
        weights_vol.commit()
        self.load_time = time.time() - t0
        print(f"[modal] model loaded in {self.load_time:.1f}s, dtype={self.dtype}, gpu={torch.cuda.get_device_name()}")

    @modal.method()
    def infer(self, frames: dict) -> bytes:
        """frames: {filename: jpeg_bytes}. Returns npz bytes."""
        import torch, numpy as np, tempfile
        from vggt.utils.load_fn import load_and_preprocess_images
        from vggt.utils.pose_enc import pose_encoding_to_extri_intri
        from vggt.utils.geometry import unproject_depth_map_to_point_map

        t_all = time.time()
        with tempfile.TemporaryDirectory() as td:
            paths = []
            for name in sorted(frames):
                p = os.path.join(td, name)
                with open(p, "wb") as f:
                    f.write(frames[name])
                paths.append(p)
            images = load_and_preprocess_images(paths).to(self.device)  # (S,3,H,W), long edge 518
        print(f"[modal] images tensor {tuple(images.shape)}")

        torch.cuda.reset_peak_memory_stats()
        torch.cuda.synchronize(); t0 = time.time()
        with torch.no_grad():
            with torch.cuda.amp.autocast(dtype=self.dtype):
                aggregated_tokens_list, ps_idx = self.model.aggregator(images[None])
            pose_enc = self.model.camera_head(aggregated_tokens_list)[-1]
            extrinsic, intrinsic = pose_encoding_to_extri_intri(pose_enc, images.shape[-2:])
            depth_map, depth_conf = self.model.depth_head(aggregated_tokens_list, images[None], ps_idx)
            point_map, point_conf = self.model.point_head(aggregated_tokens_list, images[None], ps_idx)
        torch.cuda.synchronize(); infer_time = time.time() - t0
        peak_gb = torch.cuda.max_memory_allocated() / 1e9

        ext = extrinsic[0].float().cpu().numpy()      # (S,3,4) world->cam (OpenCV)
        intr = intrinsic[0].float().cpu().numpy()     # (S,3,3)
        depth = depth_map[0].float().cpu().numpy()    # (S,H,W,1)
        dconf = depth_conf[0].float().cpu().numpy()   # (S,H,W)
        wp = point_map[0].float().cpu().numpy()       # (S,H,W,3)
        wpc = point_conf[0].float().cpu().numpy()     # (S,H,W)
        # points from depth + camera (usually more accurate than point head, per VGGT README)
        wp_from_depth = unproject_depth_map_to_point_map(depth, ext, intr)  # (S,H,W,3)
        imgs = (images.float().cpu().numpy().transpose(0, 2, 3, 1) * 255).astype(np.uint8)

        buf = io.BytesIO()
        np.savez_compressed(
            buf, extrinsic=ext, intrinsic=intr, depth=depth[..., 0].astype(np.float16), depth_conf=dconf.astype(np.float16),
            world_points=wp.astype(np.float32), world_points_conf=wpc.astype(np.float16),
            world_points_from_depth=wp_from_depth.astype(np.float32), images=imgs,
            timings=np.array([self.load_time, infer_time, time.time() - t_all, peak_gb]),
        )
        print(f"[modal] inference {infer_time:.2f}s, peak VRAM {peak_gb:.2f} GB, total in-fn {time.time()-t_all:.1f}s")
        return buf.getvalue()


@app.local_entrypoint()
def main(frames_dir: str = "frames", out: str = "out/vggt_out.npz", max_frames: int = 40):
    t0 = time.time()
    paths = sorted(glob.glob(os.path.join(frames_dir, "*.jpg")))[:max_frames]
    frames = {os.path.basename(p): open(p, "rb").read() for p in paths}
    print(f"[local] uploading {len(frames)} frames ({sum(map(len, frames.values()))/1e6:.1f} MB)")
    t1 = time.time()
    data = VGGTRunner().infer.remote(frames)
    t2 = time.time()
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "wb") as f:
        f.write(data)
    import numpy as np
    tm = np.load(io.BytesIO(data))["timings"]
    print(f"[local] saved {out} ({len(data)/1e6:.1f} MB)")
    print(f"[timing] model load (cold): {tm[0]:.1f}s | GPU inference: {tm[1]:.2f}s | remote fn total: {tm[2]:.1f}s | peak VRAM: {tm[3]:.2f} GB")
    print(f"[timing] remote call wall (incl. container cold start+upload+download): {t2-t1:.1f}s | script total: {t2-t0:.1f}s")

#!/usr/bin/env python3
"""Generate 2D projection videos from TallBoxSf chemistry simulation plotfiles.

Fields: gas density, total C12, SNII C12, WR C12, AGB C12
"""
import argparse, glob, os, shutil, subprocess, sys
import matplotlib; matplotlib.use('Agg')
from matplotlib.colors import LogNorm, Normalize
import matplotlib.pyplot as plt
import numpy as np
import yt

KPC_IN_CM = 3.085677581e21
LOG_DYNAMIC_RANGE = 1.0e6

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--plotdir', default='tests/tallbox_chem')
    p.add_argument('--outdir', default='tests/tallbox_chem/videos')
    p.add_argument('--fps', type=int, default=4)
    p.add_argument('--ffmpeg', default=None, help='Path to ffmpeg. Defaults to PATH, FFMPEG, or common Homebrew locations.')
    args = p.parse_args()
    ffmpeg = resolve_ffmpeg(args.ffmpeg)

    plts = sorted([d for d in glob.glob(os.path.join(args.plotdir, 'plt*'))
                   if os.path.isdir(d) and '.old.' not in os.path.basename(d)])
    if not plts:
        print('No plotfiles found')
        sys.exit(1)
    print(f'Found {len(plts)} plotfiles')

    os.makedirs(args.outdir, exist_ok=True)
    clean_generated_outputs(args.outdir)

    channels = [
        ('gasDensity', 'Gas Density', 'viridis'),
        ('scalar_1', 'Total C12', 'inferno'),
        ('scalar_6', 'SNII C12', 'plasma'),
        ('scalar_11', 'WR C12', 'cividis'),
        ('scalar_16', 'AGB C12', 'magma'),
    ]
    field_limits = collect_field_limits(plts, channels)

    all_frames = {ch[0]: [] for ch in channels}
    combined_frames = []

    for i, pf in enumerate(plts):
        ds = yt.load(pf)
        t_myr = float(ds.current_time) / 3.15576e13

        for field, title, cmap in channels:
            fld_tuple = ('boxlib', field)
            if fld_tuple not in ds.field_list:
                continue
            image, extent, units = make_projection_image(ds, fld_tuple)
            frame_path = os.path.join(args.outdir, f'{field}_{i:04d}.png')
            save_projection_frame(image, extent, units, title, t_myr, cmap, field_limits[field], frame_path)
            all_frames[field].append(frame_path)

        # Combined 5-panel
        fig, axes = plt.subplots(2, 3, figsize=(20, 10))
        fig.suptitle(f'TallBox Chemistry -- t = {t_myr:.1f} Myr', fontsize=14)
        for j, (field, title, cmap) in enumerate(channels):
            ax = axes[j // 3][j % 3]
            fld_tuple = ('boxlib', field)
            if fld_tuple not in ds.field_list:
                ax.text(0.5, 0.5, 'N/A', transform=ax.transAxes, ha='center', va='center')
                ax.set_title(title)
                continue
            image, extent, units = make_projection_image(ds, fld_tuple)
            norm = get_norm(image, field_limits[field])
            im = ax.imshow(mask_for_norm(image, norm), origin='lower', extent=extent, cmap=get_cmap(cmap), norm=norm, aspect='equal')
            cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
            cbar.set_label(str(units))
            ax.set_title(title)
            ax.set_xlabel('x (kpc)')
            ax.set_ylabel('y (kpc)')
        axes[1][2].set_visible(False)
        plt.tight_layout()
        cframe = os.path.join(args.outdir, f'combined_{i:04d}.png')
        fig.savefig(cframe, dpi=120, bbox_inches='tight')
        plt.close(fig)
        combined_frames.append(cframe)

        if i % 3 == 0:
            print(f'  Frame {i+1}/{len(plts)}  t={t_myr:.1f} Myr')

    for field, title, cmap in channels:
        frames = all_frames[field]
        if not frames:
            continue
        vid = os.path.join(args.outdir, f'tallbox_{field}.mp4')
        flist = os.path.join(args.outdir, f'_flist_{field}.txt')
        with open(flist, 'w') as f:
            for fr in frames:
                f.write(f"file '{os.path.abspath(fr)}'\n")
                f.write(f"duration {1/args.fps}\n")
        with open(flist, 'a') as f:
            f.write(f"file '{os.path.abspath(frames[-1])}'\n")
        subprocess.run([ffmpeg, '-y', '-f', 'concat', '-safe', '0', '-i', flist,
                        '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
                        '-vf', 'scale=trunc(iw/2)*2:trunc(ih/2)*2', vid], check=True)
        os.remove(flist)
        print(f'  {title}: {vid}')

    cvid = os.path.join(args.outdir, 'tallbox_combined.mp4')
    flist = os.path.join(args.outdir, '_flist_combined.txt')
    with open(flist, 'w') as f:
        for fr in combined_frames:
            f.write(f"file '{os.path.abspath(fr)}'\n")
            f.write(f"duration {1/args.fps}\n")
    with open(flist, 'a') as f:
        f.write(f"file '{os.path.abspath(combined_frames[-1])}'\n")
    subprocess.run([ffmpeg, '-y', '-f', 'concat', '-safe', '0', '-i', flist,
                    '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
                    '-vf', 'scale=trunc(iw/2)*2:trunc(ih/2)*2', cvid], check=True)
    os.remove(flist)
    print(f'  Combined: {cvid}')
    print('\nDone!')

def resolve_ffmpeg(requested):
    candidates = [requested, os.environ.get('FFMPEG'), shutil.which('ffmpeg'), '/opt/homebrew/bin/ffmpeg', '/usr/local/bin/ffmpeg']
    for candidate in candidates:
        if candidate and os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    raise SystemExit('ffmpeg not found. Install ffmpeg, add it to PATH, or pass --ffmpeg /path/to/ffmpeg.')

def clean_generated_outputs(outdir):
    patterns = [
        'combined_*.png',
        'gasDensity_*.png',
        'scalar_*_*.png',
        '_flist_*.txt',
        'tallbox_*.mp4',
    ]
    for pattern in patterns:
        for path in glob.glob(os.path.join(outdir, pattern)):
            if os.path.isfile(path):
                os.remove(path)

def collect_field_limits(plts, channels):
    limits = {field: {'min': np.inf, 'max': -np.inf} for field, _, _ in channels}
    for pf in plts:
        ds = yt.load(pf)
        for field, _, _ in channels:
            fld_tuple = ('boxlib', field)
            if fld_tuple not in ds.field_list:
                continue
            image, _, _ = make_projection_image(ds, fld_tuple)
            finite = image[np.isfinite(image)]
            if finite.size == 0:
                continue
            positive = finite[finite > 0.0]
            if positive.size > 0:
                limits[field]['min'] = min(limits[field]['min'], float(np.min(positive)))
            limits[field]['max'] = max(limits[field]['max'], float(np.max(finite)))
    return limits

def make_projection_image(ds, field):
    proj = ds.proj(field, 'z')
    x_width = float(ds.domain_right_edge[0] - ds.domain_left_edge[0])
    y_width = float(ds.domain_right_edge[1] - ds.domain_left_edge[1])
    nx = int(ds.domain_dimensions[0])
    ny = int(ds.domain_dimensions[1])
    frb = proj.to_frb((x_width, 'cm'), (nx, ny), height=(y_width, 'cm'))
    image = np.asarray(frb[field])
    extent = [
        float(ds.domain_left_edge[0]) / KPC_IN_CM,
        float(ds.domain_right_edge[0]) / KPC_IN_CM,
        float(ds.domain_left_edge[1]) / KPC_IN_CM,
        float(ds.domain_right_edge[1]) / KPC_IN_CM,
    ]
    return image, extent, frb[field].units

def save_projection_frame(image, extent, units, title, t_myr, cmap, limits, frame_path):
    fig, ax = plt.subplots(figsize=(8, 7))
    norm = get_norm(image, limits)
    im = ax.imshow(mask_for_norm(image, norm), origin='lower', extent=extent, cmap=get_cmap(cmap), norm=norm, aspect='equal')
    cbar = fig.colorbar(im, ax=ax)
    cbar.set_label(str(units))
    ax.set_title(f'{title}  t={t_myr:.1f} Myr')
    ax.set_xlabel('x (kpc)')
    ax.set_ylabel('y (kpc)')
    fig.savefig(frame_path, dpi=140, bbox_inches='tight')
    plt.close(fig)

def get_norm(image, limits):
    vmax = limits['max']
    if not np.isfinite(vmax):
        return Normalize(vmin=0.0, vmax=1.0)
    if vmax > 0.0:
        positive_min = limits['min']
        if np.isfinite(positive_min) and positive_min > 0.0:
            vmin = max(positive_min, vmax / LOG_DYNAMIC_RANGE)
            if vmax > vmin:
                return LogNorm(vmin=vmin, vmax=vmax)
    finite = image[np.isfinite(image)]
    if finite.size == 0:
        return Normalize(vmin=0.0, vmax=1.0)
    vmin = min(float(np.min(finite)), 0.0)
    vmax = max(float(np.max(finite)), 1.0)
    if vmax == vmin:
        if vmax == 0.0:
            return Normalize(vmin=0.0, vmax=1.0)
        delta = abs(vmax) * 0.05
        vmin -= delta
        vmax += delta
    return Normalize(vmin=vmin, vmax=vmax)

def mask_for_norm(image, norm):
    if isinstance(norm, LogNorm):
        return np.ma.masked_less_equal(image, norm.vmin)
    return image

def get_cmap(cmap):
    cmap_obj = plt.get_cmap(cmap).copy()
    cmap_obj.set_bad('black')
    cmap_obj.set_under('black')
    return cmap_obj

if __name__ == '__main__':
    main()

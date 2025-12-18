#!/usr/bin/env python3
"""
Fractal Heat Spreader Pattern Generator
Generates topology-optimized fractal patterns for thermal management wafers
Optimized for space solar, AI compute, and quantum computing applications
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Circle
from scipy.spatial import Voronoi
import json
from dataclasses import dataclass, asdict
from typing import List, Tuple
import svgwrite
from pathlib import Path


@dataclass
class WaferSpec:
    """Wafer specifications for different variants"""
    name: str
    diameter_mm: float
    operating_temp_range: Tuple[float, float]
    peak_power_density_W_cm2: float
    channel_width_um: float
    channel_depth_um: float
    material_thermal_conductivity: float  # W/m·K


# Variant specifications
SPACE_VARIANT = WaferSpec(
    name="Space Solar",
    diameter_mm=300.0,
    operating_temp_range=(-150, 150),
    peak_power_density_W_cm2=50.0,
    channel_width_um=500.0,
    channel_depth_um=200.0,
    material_thermal_conductivity=1200.0
)

AI_VARIANT = WaferSpec(
    name="AI Compute",
    diameter_mm=450.0,
    operating_temp_range=(-40, 125),
    peak_power_density_W_cm2=500.0,
    channel_width_um=200.0,
    channel_depth_um=200.0,
    material_thermal_conductivity=2000.0
)

QUANTUM_VARIANT = WaferSpec(
    name="Quantum",
    diameter_mm=200.0,
    operating_temp_range=(4, 300),
    peak_power_density_W_cm2=10.0,
    channel_width_um=300.0,
    channel_depth_um=150.0,
    material_thermal_conductivity=1500.0
)


class FractalPatternGenerator:
    """Generate optimized fractal heat spreader patterns"""
    
    def __init__(self, spec: WaferSpec, resolution: int = 2000):
        self.spec = spec
        self.resolution = resolution
        self.radius_mm = spec.diameter_mm / 2.0
        self.pattern = None
        self.hot_spots = []
        self.channels = []
        
    def add_hot_spot(self, x_mm: float, y_mm: float, intensity: float):
        """Add a heat source location with intensity (W/cm²)"""
        self.hot_spots.append((x_mm, y_mm, intensity))
        
    def generate_voronoi_fractal(self, num_points: int = 500, 
                                  iterations: int = 3) -> np.ndarray:
        """
        Generate Voronoi-based fractal pattern
        Optimized for uniform heat distribution
        """
        # Create weighted random points biased toward hot spots
        points = []
        
        # Add points weighted toward hot spots
        for _ in range(num_points):
            if self.hot_spots and np.random.random() < 0.6:
                # 60% of points near hot spots
                hot_spot = self.hot_spots[np.random.randint(len(self.hot_spots))]
                x = hot_spot[0] + np.random.normal(0, 5)
                y = hot_spot[1] + np.random.normal(0, 5)
            else:
                # Uniform distribution
                angle = np.random.uniform(0, 2 * np.pi)
                r = np.random.uniform(0, self.radius_mm)
                x = r * np.cos(angle)
                y = r * np.sin(angle)
            
            # Check if point is within wafer
            if np.sqrt(x**2 + y**2) <= self.radius_mm:
                points.append([x, y])
        
        points = np.array(points)
        
        # Generate Voronoi diagram
        vor = Voronoi(points)
        
        # Extract channel network from Voronoi edges
        channels = []
        for ridge in vor.ridge_vertices:
            if -1 not in ridge:
                v1, v2 = ridge
                p1 = vor.vertices[v1]
                p2 = vor.vertices[v2]
                
                # Check if both points within wafer
                if (np.sqrt(p1[0]**2 + p1[1]**2) <= self.radius_mm and
                    np.sqrt(p2[0]**2 + p2[1]**2) <= self.radius_mm):
                    channels.append((tuple(p1), tuple(p2)))
        
        self.channels = channels
        return channels
    
    def generate_hilbert_fractal(self, order: int = 5) -> List[Tuple]:
        """
        Generate Hilbert curve fractal pattern
        Excellent for space-filling thermal distribution
        """
        def hilbert_curve(order, orientation=0):
            """Recursive Hilbert curve generation"""
            if order == 0:
                return []
            
            # Recursive pattern based on orientation
            curve = []
            
            # Base transformations
            if orientation == 0:
                curve.extend(hilbert_curve(order - 1, 1))
                curve.append((0, 1))
                curve.extend(hilbert_curve(order - 1, 0))
                curve.append((1, 0))
                curve.extend(hilbert_curve(order - 1, 0))
                curve.append((0, -1))
                curve.extend(hilbert_curve(order - 1, 3))
            elif orientation == 1:
                curve.extend(hilbert_curve(order - 1, 0))
                curve.append((1, 0))
                curve.extend(hilbert_curve(order - 1, 1))
                curve.append((0, 1))
                curve.extend(hilbert_curve(order - 1, 1))
                curve.append((-1, 0))
                curve.extend(hilbert_curve(order - 1, 2))
            elif orientation == 2:
                curve.extend(hilbert_curve(order - 1, 3))
                curve.append((0, -1))
                curve.extend(hilbert_curve(order - 1, 2))
                curve.append((-1, 0))
                curve.extend(hilbert_curve(order - 1, 2))
                curve.append((0, 1))
                curve.extend(hilbert_curve(order - 1, 1))
            else:  # orientation == 3
                curve.extend(hilbert_curve(order - 1, 2))
                curve.append((-1, 0))
                curve.extend(hilbert_curve(order - 1, 3))
                curve.append((0, -1))
                curve.extend(hilbert_curve(order - 1, 3))
                curve.append((1, 0))
                curve.extend(hilbert_curve(order - 1, 0))
            
            return curve
        
        # Generate base Hilbert curve
        moves = hilbert_curve(order)
        
        # Convert to coordinates
        x, y = 0, 0
        path = [(x, y)]
        
        for dx, dy in moves:
            x += dx
            y += dy
            path.append((x, y))
        
        # Scale to wafer size
        path = np.array(path)
        path_min = path.min(axis=0)
        path_max = path.max(axis=0)
        path_range = path_max - path_min
        
        # Scale to fit wafer with margin
        scale = (self.radius_mm * 1.8) / path_range.max()
        path = (path - path_min - path_range / 2) * scale
        
        # Convert to channel segments
        channels = []
        for i in range(len(path) - 1):
            p1 = tuple(path[i])
            p2 = tuple(path[i + 1])
            if (np.sqrt(p1[0]**2 + p1[1]**2) <= self.radius_mm and
                np.sqrt(p2[0]**2 + p2[1]**2) <= self.radius_mm):
                channels.append((p1, p2))
        
        self.channels = channels
        return channels
    
    def generate_radial_fractal(self, num_primary: int = 16, 
                               branch_factor: int = 3) -> List[Tuple]:
        """
        Generate radial branching fractal pattern
        Optimal for centralized heat sources
        """
        channels = []
        
        # Primary radial channels
        for i in range(num_primary):
            angle = 2 * np.pi * i / num_primary
            x1, y1 = 0.0, 0.0
            x2 = self.radius_mm * np.cos(angle)
            y2 = self.radius_mm * np.sin(angle)
            channels.append(((x1, y1), (x2, y2)))
            
            # Add branching
            for r in np.linspace(0.3, 0.9, branch_factor):
                branch_x = r * self.radius_mm * np.cos(angle)
                branch_y = r * self.radius_mm * np.sin(angle)
                
                # Branch to adjacent primary channels
                next_angle = 2 * np.pi * (i + 0.5) / num_primary
                branch_end_x = (r + 0.1) * self.radius_mm * np.cos(next_angle)
                branch_end_y = (r + 0.1) * self.radius_mm * np.sin(next_angle)
                
                if np.sqrt(branch_end_x**2 + branch_end_y**2) <= self.radius_mm:
                    channels.append(((branch_x, branch_y), 
                                   (branch_end_x, branch_end_y)))
        
        self.channels = channels
        return channels
    
    def add_diamond_islands(self, num_islands: int = 20) -> List[Tuple]:
        """
        Generate positions for CVD diamond islands at predicted hot spots
        Returns list of (x, y, radius_mm) for each island
        """
        islands = []
        
        if self.hot_spots:
            # Place islands at hot spots
            for x, y, intensity in self.hot_spots:
                # Island size proportional to intensity
                radius = 2.0 + (intensity / 100.0) * 3.0  # 2-5mm radius
                islands.append((x, y, radius))
        
        # Add additional islands at high-stress areas
        islands.append((0.0, 0.0, 4.0))  # Center island
        
        # Distributed islands
        for i in range(max(0, num_islands - len(islands))):
            angle = 2 * np.pi * i / (num_islands - len(islands))
            r = self.radius_mm * 0.6
            x = r * np.cos(angle)
            y = r * np.sin(angle)
            islands.append((x, y, 2.5))
        
        return islands
    
    def export_dxf(self, filename: str):
        """Export pattern to DXF format for CAM"""
        try:
            import ezdxf
        except ImportError:
            print("ezdxf not installed. Installing...")
            import subprocess
            subprocess.run(['pip', 'install', 'ezdxf', '--break-system-packages'], 
                         check=True)
            import ezdxf
        
        doc = ezdxf.new('R2010')
        msp = doc.modelspace()
        
        # Add wafer outline
        msp.add_circle((0, 0), self.radius_mm, dxfattribs={'layer': 'WAFER_OUTLINE'})
        
        # Add channels
        for p1, p2 in self.channels:
            msp.add_line(p1, p2, dxfattribs={'layer': 'CHANNELS'})
        
        # Add diamond islands
        islands = self.add_diamond_islands()
        for x, y, r in islands:
            msp.add_circle((x, y), r, dxfattribs={'layer': 'DIAMOND_ISLANDS'})
        
        # Add heat pipe locations
        num_pipes = int(self.spec.diameter_mm / 5)  # Every 5mm
        for i in range(num_pipes):
            for j in range(num_pipes):
                x = (i - num_pipes/2) * 5
                y = (j - num_pipes/2) * 5
                if np.sqrt(x**2 + y**2) <= self.radius_mm:
                    msp.add_circle((x, y), 0.25, 
                                 dxfattribs={'layer': 'HEAT_PIPES'})
        
        doc.saveas(filename)
        print(f"DXF exported to {filename}")
    
    def export_svg(self, filename: str):
        """Export pattern to SVG for visualization"""
        width = int(self.spec.diameter_mm * 10)
        height = width
        
        dwg = svgwrite.Drawing(filename, size=(f'{width}px', f'{height}px'), 
                              profile='tiny')
        
        # Transform: shift origin to center
        offset = width / 2
        
        def transform(x, y):
            return (x * 10 + offset, -y * 10 + offset)
        
        # Wafer outline
        dwg.add(dwg.circle(center=(offset, offset), 
                          r=self.radius_mm * 10,
                          fill='lightgray', stroke='black', 
                          stroke_width=2))
        
        # Channels
        for p1, p2 in self.channels:
            x1, y1 = transform(p1[0], p1[1])
            x2, y2 = transform(p2[0], p2[1])
            dwg.add(dwg.line(start=(x1, y1), end=(x2, y2),
                           stroke='blue', stroke_width=1))
        
        # Diamond islands
        islands = self.add_diamond_islands()
        for x, y, r in islands:
            cx, cy = transform(x, y)
            dwg.add(dwg.circle(center=(cx, cy), r=r * 10,
                             fill='orange', fill_opacity=0.5,
                             stroke='darkorange', stroke_width=1))
        
        # Hot spots
        for x, y, intensity in self.hot_spots:
            cx, cy = transform(x, y)
            dwg.add(dwg.circle(center=(cx, cy), r=30,
                             fill='red', fill_opacity=0.7))
        
        dwg.save()
        print(f"SVG exported to {filename}")
    
    def export_json(self, filename: str):
        """Export pattern data to JSON"""
        data = {
            'wafer_spec': asdict(self.spec),
            'channels': [[list(p1), list(p2)] for p1, p2 in self.channels],
            'diamond_islands': [(float(x), float(y), float(r)) for x, y, r in self.add_diamond_islands()],
            'hot_spots': self.hot_spots,
            'metadata': {
                'num_channels': len(self.channels),
                'total_channel_length_mm': float(sum(
                    np.sqrt((p2[0]-p1[0])**2 + (p2[1]-p1[1])**2) 
                    for p1, p2 in self.channels
                )),
                'channel_width_um': self.spec.channel_width_um,
                'channel_depth_um': self.spec.channel_depth_um
            }
        }
        
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"JSON data exported to {filename}")
    
    def visualize(self, filename: str = None):
        """Create visualization plot"""
        fig, ax = plt.subplots(figsize=(12, 12))
        
        # Wafer outline
        circle = Circle((0, 0), self.radius_mm, fill=False, 
                       edgecolor='black', linewidth=2)
        ax.add_patch(circle)
        
        # Channels
        for p1, p2 in self.channels:
            ax.plot([p1[0], p2[0]], [p1[1], p2[1]], 
                   'b-', linewidth=0.5, alpha=0.6)
        
        # Diamond islands
        islands = self.add_diamond_islands()
        for x, y, r in islands:
            circle = Circle((x, y), r, fill=True, 
                          facecolor='orange', alpha=0.5, 
                          edgecolor='darkorange', linewidth=1)
            ax.add_patch(circle)
        
        # Hot spots
        if self.hot_spots:
            hot_x = [h[0] for h in self.hot_spots]
            hot_y = [h[1] for h in self.hot_spots]
            hot_i = [h[2] for h in self.hot_spots]
            scatter = ax.scatter(hot_x, hot_y, c=hot_i, cmap='hot', 
                               s=200, alpha=0.7, edgecolor='red', linewidth=2)
            plt.colorbar(scatter, ax=ax, label='Power Density (W/cm²)')
        
        ax.set_xlim(-self.radius_mm * 1.1, self.radius_mm * 1.1)
        ax.set_ylim(-self.radius_mm * 1.1, self.radius_mm * 1.1)
        ax.set_aspect('equal')
        ax.grid(True, alpha=0.3)
        ax.set_xlabel('X (mm)')
        ax.set_ylabel('Y (mm)')
        ax.set_title(f'{self.spec.name} Thermal Management Wafer\n'
                    f'Fractal Heat Spreader Pattern')
        
        if filename:
            plt.savefig(filename, dpi=300, bbox_inches='tight')
            print(f"Visualization saved to {filename}")
        else:
            plt.show()
        
        plt.close()


def generate_all_variants():
    """Generate optimized patterns for all three variants"""
    output_dir = Path('/home/claude/thermal_wafer_project/cad_models')
    
    variants = [
        (SPACE_VARIANT, 'voronoi'),
        (AI_VARIANT, 'hilbert'),
        (QUANTUM_VARIANT, 'radial')
    ]
    
    for spec, pattern_type in variants:
        print(f"\n{'='*60}")
        print(f"Generating {spec.name} variant with {pattern_type} pattern")
        print(f"{'='*60}")
        
        gen = FractalPatternGenerator(spec)
        
        # Add hot spots based on variant
        if spec.name == "Space Solar":
            # Distributed solar cell hot spots
            for i in range(12):
                angle = 2 * np.pi * i / 12
                r = spec.diameter_mm / 2 * 0.7
                x = r * np.cos(angle)
                y = r * np.sin(angle)
                gen.add_hot_spot(x, y, 50.0)
        
        elif spec.name == "AI Compute":
            # Central processing core with high-density hot spots
            gen.add_hot_spot(0, 0, 500.0)
            for i in range(8):
                angle = 2 * np.pi * i / 8
                r = 30
                x = r * np.cos(angle)
                y = r * np.sin(angle)
                gen.add_hot_spot(x, y, 300.0)
        
        elif spec.name == "Quantum":
            # Precision qubit array hot spots
            for i in range(-3, 4):
                for j in range(-3, 4):
                    if i**2 + j**2 <= 9:
                        gen.add_hot_spot(i * 15, j * 15, 10.0)
        
        # Generate pattern
        if pattern_type == 'voronoi':
            gen.generate_voronoi_fractal(num_points=500)
        elif pattern_type == 'hilbert':
            gen.generate_hilbert_fractal(order=6)
        else:  # radial
            gen.generate_radial_fractal(num_primary=24, branch_factor=4)
        
        # Export all formats
        base_name = spec.name.lower().replace(' ', '_')
        gen.export_dxf(str(output_dir / f'{base_name}_pattern.dxf'))
        gen.export_svg(str(output_dir / f'{base_name}_pattern.svg'))
        gen.export_json(str(output_dir / f'{base_name}_pattern.json'))
        gen.visualize(str(output_dir / f'{base_name}_pattern.png'))
        
        print(f"\nFiles generated for {spec.name}:")
        print(f"  - {base_name}_pattern.dxf (CAM manufacturing)")
        print(f"  - {base_name}_pattern.svg (visualization)")
        print(f"  - {base_name}_pattern.json (simulation data)")
        print(f"  - {base_name}_pattern.png (preview image)")


if __name__ == '__main__':
    # Install required packages
    import subprocess
    packages = ['svgwrite', 'ezdxf']
    for pkg in packages:
        try:
            __import__(pkg)
        except ImportError:
            print(f"Installing {pkg}...")
            subprocess.run(['pip', 'install', pkg, '--break-system-packages'], 
                         check=True)
    
    generate_all_variants()
    
    print("\n" + "="*60)
    print("All fractal patterns generated successfully!")
    print("="*60)

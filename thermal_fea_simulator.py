#!/usr/bin/env python3
"""
Thermal Management Wafer FEA Simulation
Finite Element Analysis for thermal distribution across wafer designs
Supports all three variants: Space Solar, AI Compute, Quantum
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib import cm
from scipy.sparse import lil_matrix, csr_matrix
from scipy.sparse.linalg import spsolve
import json
from pathlib import Path
from dataclasses import dataclass
from typing import List, Tuple, Dict
import time


@dataclass
class ThermalProperties:
    """Material thermal properties"""
    conductivity: float  # W/m·K
    density: float  # kg/m³
    specific_heat: float  # J/kg·K
    emissivity: float = 0.9  # for radiative cooling


# Material properties database
MATERIALS = {
    'aluminum_nitride': ThermalProperties(170.0, 3260, 740, 0.9),
    'copper': ThermalProperties(400.0, 8960, 385, 0.05),
    'diamond_copper_composite': ThermalProperties(1200.0, 7500, 420, 0.7),
    'cvd_diamond': ThermalProperties(2000.0, 3520, 509, 0.85),
    'silicon': ThermalProperties(148.0, 2329, 712, 0.7),
}


class ThermalFEA:
    """Finite Element Analysis for thermal distribution"""
    
    def __init__(self, wafer_diameter_mm: float, resolution: int = 200):
        """
        Initialize FEA mesh
        
        Args:
            wafer_diameter_mm: Wafer diameter in mm
            resolution: Number of mesh points along diameter
        """
        self.diameter_mm = wafer_diameter_mm
        self.radius_mm = wafer_diameter_mm / 2.0
        self.resolution = resolution
        
        # Create 2D mesh
        self.dx = self.diameter_mm / resolution
        x = np.linspace(-self.radius_mm, self.radius_mm, resolution)
        y = np.linspace(-self.radius_mm, self.radius_mm, resolution)
        self.X, self.Y = np.meshgrid(x, y)
        
        # Create mask for circular wafer
        self.mask = (self.X**2 + self.Y**2) <= self.radius_mm**2
        
        # Initialize fields
        self.temperature = np.zeros_like(self.X)
        self.heat_sources = np.zeros_like(self.X)
        self.conductivity_map = np.ones_like(self.X) * MATERIALS['copper'].conductivity
        
        # Channel network
        self.channels = []
        self.diamond_islands = []
        
        self.n = resolution
        self.num_nodes = resolution * resolution
    
    def load_pattern_from_json(self, json_file: str):
        """Load fractal pattern from JSON file"""
        with open(json_file, 'r') as f:
            data = json.load(f)
        
        self.channels = [
            (np.array(p1), np.array(p2)) 
            for p1, p2 in data['channels']
        ]
        
        self.diamond_islands = [
            (x, y, r) for x, y, r in data['diamond_islands']
        ]
        
        # Apply enhanced conductivity to channels
        self._apply_channel_conductivity()
        
        # Apply diamond island conductivity
        self._apply_diamond_islands()
        
        print(f"Loaded pattern with {len(self.channels)} channels "
              f"and {len(self.diamond_islands)} diamond islands")
    
    def _apply_channel_conductivity(self, channel_width_mm: float = 0.5):
        """Apply enhanced conductivity along channel network"""
        # Heat pipes have effective conductivity of ~15000 W/m·K
        heat_pipe_k = 15000.0
        
        for p1, p2 in self.channels:
            # Rasterize line
            num_points = int(np.linalg.norm(p2 - p1) / self.dx) + 1
            for t in np.linspace(0, 1, num_points):
                point = p1 + t * (p2 - p1)
                
                # Find mesh indices
                i = int((point[0] + self.radius_mm) / self.dx)
                j = int((point[1] + self.radius_mm) / self.dx)
                
                if (0 <= i < self.n and 0 <= j < self.n and self.mask[j, i]):
                    # Apply enhanced conductivity in region around channel
                    for di in range(-2, 3):
                        for dj in range(-2, 3):
                            ii, jj = i + di, j + dj
                            if (0 <= ii < self.n and 0 <= jj < self.n 
                                and self.mask[jj, ii]):
                                self.conductivity_map[jj, ii] = heat_pipe_k
    
    def _apply_diamond_islands(self):
        """Apply CVD diamond thermal conductivity at island locations"""
        diamond_k = MATERIALS['cvd_diamond'].conductivity
        
        for x, y, r in self.diamond_islands:
            # Convert to mesh coordinates
            for i in range(self.n):
                for j in range(self.n):
                    if not self.mask[j, i]:
                        continue
                    
                    mesh_x = -self.radius_mm + i * self.dx
                    mesh_y = -self.radius_mm + j * self.dx
                    
                    dist = np.sqrt((mesh_x - x)**2 + (mesh_y - y)**2)
                    if dist <= r:
                        self.conductivity_map[j, i] = diamond_k
    
    def add_heat_source(self, x_mm: float, y_mm: float, 
                       power_W: float, radius_mm: float = 5.0):
        """Add a heat source to the simulation"""
        for i in range(self.n):
            for j in range(self.n):
                if not self.mask[j, i]:
                    continue
                
                mesh_x = -self.radius_mm + i * self.dx
                mesh_y = -self.radius_mm + j * self.dx
                
                dist = np.sqrt((mesh_x - x_mm)**2 + (mesh_y - y_mm)**2)
                if dist <= radius_mm:
                    # Gaussian heat distribution
                    self.heat_sources[j, i] += (power_W / (np.pi * radius_mm**2)) * \
                        np.exp(-dist**2 / (2 * (radius_mm/3)**2))
    
    def set_boundary_conditions(self, ambient_temp_C: float, 
                               cooling_type: str = 'convective'):
        """
        Set boundary conditions
        
        Args:
            ambient_temp_C: Ambient temperature
            cooling_type: 'convective', 'radiative', or 'liquid'
        """
        self.ambient_temp = ambient_temp_C
        self.cooling_type = cooling_type
        
        # Heat transfer coefficients (W/m²·K)
        self.h_coefficients = {
            'convective': 10.0,     # Natural air convection
            'radiative': 5.0,       # Radiative in space
            'liquid': 5000.0,       # Liquid cooling
        }
        
        self.h = self.h_coefficients.get(cooling_type, 10.0)
    
    def build_stiffness_matrix(self) -> csr_matrix:
        """Build global stiffness matrix for steady-state heat equation"""
        print("Building stiffness matrix...")
        start_time = time.time()
        
        # Sparse matrix for efficiency
        K = lil_matrix((self.num_nodes, self.num_nodes))
        
        # Finite difference stencil
        dx = self.dx / 1000.0  # Convert to meters
        
        for i in range(self.n):
            for j in range(self.n):
                if not self.mask[j, i]:
                    continue
                
                idx = j * self.n + i
                k = self.conductivity_map[j, i]
                
                # Central node
                K[idx, idx] = -4 * k / (dx**2)
                
                # Neighbors (4-point stencil)
                neighbors = [
                    (i+1, j, 1), (i-1, j, 1),
                    (i, j+1, 1), (i, j-1, 1)
                ]
                
                for ni, nj, weight in neighbors:
                    if (0 <= ni < self.n and 0 <= nj < self.n 
                        and self.mask[nj, ni]):
                        nidx = nj * self.n + ni
                        K[idx, nidx] = k / (dx**2) * weight
                
                # Boundary conditions (Robin/convective)
                if self._is_boundary(i, j):
                    K[idx, idx] += -self.h / dx
        
        print(f"Stiffness matrix built in {time.time() - start_time:.2f}s")
        return K.tocsr()
    
    def _is_boundary(self, i: int, j: int) -> bool:
        """Check if node is on wafer boundary"""
        mesh_x = -self.radius_mm + i * self.dx
        mesh_y = -self.radius_mm + j * self.dx
        dist = np.sqrt(mesh_x**2 + mesh_y**2)
        return abs(dist - self.radius_mm) < 2 * self.dx
    
    def build_force_vector(self) -> np.ndarray:
        """Build force vector from heat sources and boundary conditions"""
        F = np.zeros(self.num_nodes)
        
        dx = self.dx / 1000.0  # Convert to meters
        
        for i in range(self.n):
            for j in range(self.n):
                if not self.mask[j, i]:
                    continue
                
                idx = j * self.n + i
                
                # Heat source term
                F[idx] = -self.heat_sources[j, i] * dx**2
                
                # Boundary condition (ambient temperature)
                if self._is_boundary(i, j):
                    F[idx] += -self.h * self.ambient_temp / dx
        
        return F
    
    def solve_steady_state(self) -> np.ndarray:
        """Solve steady-state heat equation"""
        print("Solving steady-state thermal distribution...")
        start_time = time.time()
        
        # Build system
        K = self.build_stiffness_matrix()
        F = self.build_force_vector()
        
        # Solve K*T = F
        T_vector = spsolve(K, F)
        
        # Reshape to 2D
        self.temperature = T_vector.reshape((self.n, self.n))
        
        # Apply mask
        self.temperature[~self.mask] = self.ambient_temp
        
        print(f"Solution computed in {time.time() - start_time:.2f}s")
        print(f"Temperature range: {self.temperature[self.mask].min():.1f}°C "
              f"to {self.temperature[self.mask].max():.1f}°C")
        print(f"Max ΔT: {self.temperature[self.mask].max() - self.temperature[self.mask].min():.1f}°C")
        
        return self.temperature
    
    def solve_transient(self, total_time_s: float, dt: float = 0.1) -> List[np.ndarray]:
        """
        Solve transient heat equation
        
        Args:
            total_time_s: Total simulation time
            dt: Time step size
        
        Returns:
            List of temperature fields at each time step
        """
        print(f"Solving transient thermal response for {total_time_s}s...")
        
        # Material properties (use composite values)
        rho = MATERIALS['diamond_copper_composite'].density
        cp = MATERIALS['diamond_copper_composite'].specific_heat
        
        # Build matrices
        K = self.build_stiffness_matrix()
        
        # Mass matrix (lumped)
        dx = self.dx / 1000.0
        M = lil_matrix((self.num_nodes, self.num_nodes))
        for i in range(self.num_nodes):
            M[i, i] = rho * cp * dx**2
        M = M.tocsr()
        
        # Time integration (implicit Euler)
        A = M + dt * K
        
        # Initial condition
        T_current = np.zeros(self.num_nodes)
        T_current[:] = self.ambient_temp
        
        results = []
        num_steps = int(total_time_s / dt)
        
        for step in range(num_steps):
            if step % 100 == 0:
                print(f"  Step {step}/{num_steps} ({step*dt:.1f}s)")
            
            # Build RHS
            F = self.build_force_vector()
            b = M @ T_current + dt * F
            
            # Solve
            T_current = spsolve(A, b)
            
            # Store result every 10 steps
            if step % 10 == 0:
                T_2d = T_current.reshape((self.n, self.n))
                T_2d[~self.mask] = self.ambient_temp
                results.append(T_2d.copy())
        
        self.temperature = T_current.reshape((self.n, self.n))
        self.temperature[~self.mask] = self.ambient_temp
        
        return results
    
    def visualize(self, filename: str = None, show_channels: bool = True):
        """Visualize thermal distribution"""
        fig, axes = plt.subplots(1, 2, figsize=(16, 7))
        
        # Temperature distribution
        ax = axes[0]
        temp_plot = self.temperature.copy()
        temp_plot[~self.mask] = np.nan
        
        im = ax.contourf(self.X, self.Y, temp_plot, levels=50, cmap='hot')
        plt.colorbar(im, ax=ax, label='Temperature (°C)')
        
        if show_channels and self.channels:
            for p1, p2 in self.channels[:200]:  # Limit for visibility
                ax.plot([p1[0], p2[0]], [p1[1], p2[1]], 
                       'c-', linewidth=0.3, alpha=0.3)
        
        if self.diamond_islands:
            for x, y, r in self.diamond_islands[:50]:
                circle = plt.Circle((x, y), r, fill=False, 
                                  edgecolor='cyan', linewidth=1, alpha=0.5)
                ax.add_patch(circle)
        
        ax.set_xlim(-self.radius_mm, self.radius_mm)
        ax.set_ylim(-self.radius_mm, self.radius_mm)
        ax.set_aspect('equal')
        ax.set_xlabel('X (mm)')
        ax.set_ylabel('Y (mm)')
        ax.set_title('Temperature Distribution')
        ax.grid(True, alpha=0.3)
        
        # Thermal gradient magnitude
        ax = axes[1]
        grad_x, grad_y = np.gradient(temp_plot)
        grad_mag = np.sqrt(grad_x**2 + grad_y**2)
        grad_mag[~self.mask] = np.nan
        
        im = ax.contourf(self.X, self.Y, grad_mag, levels=50, cmap='viridis')
        plt.colorbar(im, ax=ax, label='Thermal Gradient (°C/mm)')
        
        ax.set_xlim(-self.radius_mm, self.radius_mm)
        ax.set_ylim(-self.radius_mm, self.radius_mm)
        ax.set_aspect('equal')
        ax.set_xlabel('X (mm)')
        ax.set_ylabel('Y (mm)')
        ax.set_title('Thermal Gradient Magnitude')
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if filename:
            plt.savefig(filename, dpi=300, bbox_inches='tight')
            print(f"Visualization saved to {filename}")
        else:
            plt.show()
        
        plt.close()
    
    def export_results(self, filename: str):
        """Export simulation results to JSON"""
        results = {
            'wafer_diameter_mm': self.diameter_mm,
            'resolution': self.resolution,
            'ambient_temp_C': self.ambient_temp,
            'cooling_type': self.cooling_type,
            'temperature_stats': {
                'min': float(self.temperature[self.mask].min()),
                'max': float(self.temperature[self.mask].max()),
                'mean': float(self.temperature[self.mask].mean()),
                'std': float(self.temperature[self.mask].std()),
                'delta_T': float(self.temperature[self.mask].max() - 
                               self.temperature[self.mask].min())
            },
            'heat_load_W': float(np.sum(self.heat_sources) * (self.dx/1000)**2),
        }
        
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"Results exported to {filename}")


def run_all_simulations():
    """Run thermal simulations for all three variants"""
    output_dir = Path('/home/claude/thermal_wafer_project/simulations')
    cad_dir = Path('/home/claude/thermal_wafer_project/cad_models')
    
    variants = [
        {
            'name': 'space_solar',
            'diameter': 300.0,
            'pattern_file': cad_dir / 'space_solar_pattern.json',
            'ambient_temp': 25.0,
            'cooling': 'radiative',
            'heat_loads': [(0, 0, 50), (105, 0, 50), (-105, 0, 50),
                          (0, 105, 50), (0, -105, 50)]
        },
        {
            'name': 'ai_compute',
            'diameter': 450.0,
            'pattern_file': cad_dir / 'ai_compute_pattern.json',
            'ambient_temp': 25.0,
            'cooling': 'liquid',
            'heat_loads': [(0, 0, 1000)]
        },
        {
            'name': 'quantum',
            'diameter': 200.0,
            'pattern_file': cad_dir / 'quantum_pattern.json',
            'ambient_temp': -269.0,  # 4K
            'cooling': 'convective',
            'heat_loads': [(0, 0, 5), (15, 15, 5), (-15, -15, 5)]
        }
    ]
    
    for variant in variants:
        print(f"\n{'='*70}")
        print(f"Running simulation: {variant['name']}")
        print(f"{'='*70}")
        
        # Create FEA instance
        fea = ThermalFEA(variant['diameter'], resolution=150)
        
        # Load pattern
        if variant['pattern_file'].exists():
            fea.load_pattern_from_json(str(variant['pattern_file']))
        else:
            print(f"Warning: Pattern file not found, running without pattern")
        
        # Add heat sources
        for x, y, power in variant['heat_loads']:
            fea.add_heat_source(x, y, power)
        
        # Set boundary conditions
        fea.set_boundary_conditions(variant['ambient_temp'], variant['cooling'])
        
        # Solve steady state
        fea.solve_steady_state()
        
        # Visualize and export
        fea.visualize(str(output_dir / f'{variant["name"]}_thermal_steady.png'))
        fea.export_results(str(output_dir / f'{variant["name"]}_results.json'))
        
        print(f"\nSimulation complete for {variant['name']}")


if __name__ == '__main__':
    run_all_simulations()
    
    print("\n" + "="*70)
    print("All thermal simulations completed successfully!")
    print("="*70)

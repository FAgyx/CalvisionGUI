import ROOT
import numpy as np
from numpy.polynomial.chebyshev import chebval
import matplotlib.pyplot as plt

class RTFunction:
    def __init__(self, root_file, object_name="RTParam", t_min=-116.85, t_max=186.4):
        self.T0 = t_min
        self.Tmax = t_max

        # Load coefficients from ROOT file
        self._load_coefficients(root_file, object_name)

    def _load_coefficients(self, root_file, object_name):
        f = ROOT.TFile(root_file)
        if f.IsZombie():
            raise RuntimeError(f"Failed to open file: {root_file}")
        vec = f.Get(object_name)
        if not vec:
            raise RuntimeError(f"Object '{object_name}' not found in file")
        print(f"Retrieved: {vec.ClassName()}, size = {vec.GetNrows()}")
        self.params = np.array([vec[i] for i in range(vec.GetNrows())])

    def time_to_x(self, t):
        if t>=self.T0 and t<=self.Tmax:
            return (2 * t - (self.Tmax + self.T0)) / (self.Tmax - self.T0)
        else:
            return -2

    def r(self, t_input):
        """Evaluate r(t). Accepts scalar or array."""
        t_array = np.atleast_1d(t_input)
        x = self.time_to_x(t_array)
        if x>= -1:
            r_vals = chebval(x, self.params)
            return r_vals[0] if np.isscalar(t_input) else r_vals
        else:
            return -1

    def plot_r(self, num_points=500, output="r_t_plot.png"):
        """Plot r(t) over the time domain."""
        t_vals = np.linspace(self.T0, self.Tmax, num_points)
        r_vals = self.r(t_vals)

        plt.figure(figsize=(8, 5))
        plt.plot(t_vals, r_vals, label="r(t)", color="blue")
        plt.xlabel("Drift Time [ns]")
        plt.ylabel("Radius [mm]")
        plt.title("RT Function from Chebyshev Coefficients")
        plt.grid(True)
        plt.legend()
        plt.tight_layout()
        plt.savefig(output)
        plt.show()

    def draw_with_root(self):
        """Optional: draw using ROOT.TF1 on normalized domain [-1,1]"""
        f_cheb = ROOT.TF1("f_cheb", "cheb9", -1, 1)
        for i, val in enumerate(self.params):
            f_cheb.SetParameter(i, val)
        f_cheb.SetTitle("Chebyshev Polynomial (domain [-1,1]);x;r(t)")
        f_cheb.SetLineColor(ROOT.kBlue)
        f_cheb.SetLineWidth(2)
        c = ROOT.TCanvas("c", "Chebyshev Polynomial", 800, 600)
        f_cheb.Draw()
        c.SaveAs("ChebyshevPolynomial_Correct.png")

# # Example usage:
# rt = RTFunction("autoCalibratedRT_0_100000.root")
# print(rt.r(0))
# rt.plot_r()
# rt.draw_with_root()

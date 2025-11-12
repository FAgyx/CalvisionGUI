import ROOT
import sys
import os
import math
import array
from methods import *
import numpy as np
from scipy.signal import find_peaks
from scipy.signal import find_peaks_cwt
from RTFunction import RTFunction

class WaveCluster:
    def __init__(self, input_rootfile, chnls, out_folder,output_rootfile):
        """Initialize WaveCluster from input ROOT file, channel list, output folder."""
        self.wave_tree_in = getTreeFromRoot(input_rootfile)
        self.output_rootfile = output_rootfile
        if self.wave_tree_in is None:
            print("No TTree found.")
            sys.exit(0)

        self.pb_TH1s_in = getAllBranchFromTree(self.wave_tree_in)
        print(f"{len(self.pb_TH1s_in)} branch(es) loaded.")
        if not self.pb_TH1s_in:
            print("No TBranch found.")
            sys.exit(0)

        self._chnls = list(chnls)
        self.wave_tree_out = ROOT.TTree("wave_cluster_tree", "wave_cluster_tree")
        self.p_wave_template = input_rootfile.Get("waveform")
        self.out_folder = out_folder

        self.h2_cluster_vs_time = ROOT.TH2D(
            "h2_cluster_vs_time", "Cluster count vs Leading Edge Time",
            50, -200, 200,  # X-axis: time
            30, 1, 31       # Y-axis: cluster count
        )
        self.h2_cluster_vs_time.GetXaxis().SetTitle("Fastest Drift Time (ns)")
        self.h2_cluster_vs_time.GetYaxis().SetTitle("Cluster Count")
 
      

    def r_to_path_length(self,r, R=7.1):
        """Calculate chord length for drift radius r in tube of radius R."""
        r = np.asarray(r)
        if np.any(r > R):
            raise ValueError("Drift radius cannot be larger than tube radius")
        return 2 * np.sqrt(R**2 - r**2)


    def find_peak_time_radius(self, p_wave_in, peaks, Vth, rt):
        if not len(peaks):
            return -1

        peak_bin = int(peaks[0])
        max_bin = p_wave_in.GetNbinsX()

        # Step 1: Search backward to find point below threshold
        search_start = peak_bin
        while search_start > self.k_start and p_wave_in.GetBinContent(search_start) >= Vth:
            search_start -= 1

        # Step 2: Search forward to find leading edge crossing threshold
        leading_edge_bin = search_start
        while (leading_edge_bin <= peak_bin and 
               p_wave_in.GetBinContent(leading_edge_bin) < Vth):
            leading_edge_bin += 1
            if leading_edge_bin > max_bin:
                return -1

        # Step 3: Validate and calculate drift time and radius
        if leading_edge_bin < peak_bin:
            drift_time = p_wave_in.GetBinCenter(leading_edge_bin)
            drift_radius = rt.r(drift_time)
            return drift_radius if drift_radius >= 0 else -1
        else:
            return -1


    def cluster_counting_secondDeriv(self, p_wave_in, event_number, channel_number, draw):
        # --- convert TH1D to numpy arrays ---
        n_bins = p_wave_in.GetNbinsX()
        x_vals = np.array([p_wave_in.GetBinCenter(i) for i in range(1, n_bins+1)])
        y_vals = np.array([p_wave_in.GetBinContent(i) for i in range(1, n_bins+1)])

        # compute derivatives
        first_deriv  = np.gradient(y_vals, x_vals)
        second_deriv = np.gradient(first_deriv, x_vals)  # optional
        # Create TH1D for first derivative
        deriv_hist = ROOT.TH1D(f"first_deriv_evt{event_number}_ch{channel_number}",
                               "First Derivative", n_bins, x_vals[0], x_vals[-1])

        # Restrict range
        x_min, x_max = -130, 250
        indices = np.where((x_vals >= x_min) & (x_vals <= x_max))[0]
        self.k_start = p_wave_in.GetXaxis().FindBin(x_min)
        self.k_end = p_wave_in.GetXaxis().FindBin(x_max)

        # Subset for limited region
        x_limited = x_vals[indices]
        y_limited = y_vals[indices]
        y_threshold = 0.006
        second_deriv_threshold = 0.01

        first_deriv_limited = first_deriv[indices]
        second_deriv_limited = second_deriv[indices]
        second_deriv_int = [0]
        peaks_raw = []
        for i in range(1,len(x_limited)):
            second_deriv_int.append(0)
            if y_limited[i-1]>y_threshold:
                if second_deriv_limited[i] >0:
                    second_deriv_int[i]=second_deriv_int[i-1]+second_deriv_limited[i]
                elif second_deriv_int[i-1]>second_deriv_threshold:
                    peaks_raw.append(i)  # found peaks

        # Convert to full waveform indices
        peaks = indices[peaks_raw]
        
        if draw:
            self.draw_waveform_with_marker(event_number,channel_number,p_wave_in,x_vals,y_vals,peaks)
            # print(f"{len(peaks)} peaks found")

        if draw: #draw Integrated Second Derivative
            import matplotlib.pyplot as plt

            # Prepare x and y data for plotting
            second_deriv_int = np.array(second_deriv_int)  # convert to numpy array
            x_peaks = x_limited[peaks_raw]
            y_peaks = second_deriv_int[peaks_raw]

            # Plot integrated second derivative
            plt.figure(figsize=(10, 4))
            plt.plot(x_limited, second_deriv_int, label="Integrated Second Derivative", color='green')
            
            # Overlay peak markers
            plt.scatter(x_peaks, y_peaks, color='red', marker='o', s=50, label="Detected Peaks")

            plt.axhline(y=second_deriv_threshold, color='red', linestyle='--', label='Threshold')
            plt.xlabel("Time (ns)")
            plt.ylabel("Integrated 2nd Derivative")
            plt.title(f"Event {event_number}, Channel {channel_number}")
            plt.legend()
            plt.grid(True)
            plt.tight_layout()
            plt.savefig(f"{self.out_folder}/event_marked/"
                f"second_deriv_int_evt{event_number}_ch{channel_number}.png")
            plt.close()
        return peaks


    def draw_waveform_with_marker(self,event_number,channel_number,p_wave_in,x_vals,y_vals,peaks):
        c = ROOT.TCanvas(f"c_evt{event_number}_ch{channel_number}", 
                         "Waveform with electrons & clusters", 1200, 800)
        p_wave_in.SetLineColor(ROOT.kBlack)
        c.SetBottomMargin(0.15)
        c.SetLeftMargin(0.15)

        p_wave_in.Draw("hist")

        cluster_markers = []   # ? keep references to avoid GC
        
        for idx in peaks:
            x = x_vals[idx]
            y = y_vals[idx]
            m = ROOT.TMarker(x, y, 23)
            m.SetMarkerColor(ROOT.kRed)
            m.SetMarkerSize(1.2)
            m.Draw("same")
            cluster_markers.append(m)  # ? store ref

        latex = ROOT.TLatex()
        latex.SetNDC()
        latex.SetTextSize(0.08)
        latex.DrawLatex(0.75, 0.85, f"N_cl = {len(peaks)}")

        c.Update()
        c.SaveAs(f"{self.out_folder}/event_marked/"
                f"event{event_number}_chnl_{channel_number}_marked.png")


    def find_cluster(self, entries, draw_entries,rt,vth):

        self.output_rootfile.cd()

        max_entries = self.pb_TH1s_in[0].GetEntries()
        entries = max_entries if entries == 0 or entries > max_entries else entries

        # ? use array.array for branch linking
        clusters = [array.array('i', [0]) for _ in range(len(self._chnls))]
        cluster_by_radius = [
            [array.array('i', [0]) for _ in range(8)]
            for _ in range(len(self._chnls))
        ]
        dn_dx = [array.array('d', [0.0]) for _ in range(len(self._chnls))]
        dn_dx_by_radius = [
            [array.array('d', [0.0]) for _ in range(8)]
            for _ in range(len(self._chnls))
        ]

        p_wave = [self.p_wave_template.Clone() for _ in range(len(self._chnls))]



        p_output_canvas = ROOT.TCanvas("waveform", "waveform")
        p_output_canvas.SetRightMargin(0.1)

        for i, ch in enumerate(self._chnls):
            branch_name = f"waveTH1_channel{ch}_back"
            branch = self.wave_tree_in.GetBranch(branch_name)
            if not branch:
                raise RuntimeError(f"Branch {branch_name} not found in tree")
            branch.SetAddress(ROOT.AddressOf(p_wave[i]))
            # store cluster info for all and each channel in root file
            self.wave_tree_out.Branch(f"chnl{ch}_cluster", clusters[i], f"chnl{ch}_cluster/I")
            for j in range(8):
                self.wave_tree_out.Branch(
                    f"chnl{ch}_cluster_by_radius{j+1}",
                    cluster_by_radius[i][j],
                    f"chnl{ch}_cluster_by_radius{j+1}/I"
                )
            # store cluster/cm info for all and each channel in root file
            self.wave_tree_out.Branch(f"chnl{ch}_dn_dx", dn_dx[i], f"chnl{ch}_dn_dx/D")
            for j in range(8):
                self.wave_tree_out.Branch(
                    f"chnl{ch}_dn_dx_by_radius{j+1}",
                    dn_dx_by_radius[i][j],
                    f"chnl{ch}_dn_dx_by_radius{j+1}/D"
                )


        event_print = 100
        for entry in range(entries):
            draw = entry < draw_entries
            if entry % event_print == 0:
                print(f"Processed {entry} events...")
                if math.floor(math.log10(entry + 1)) > math.floor(math.log10(event_print)):
                    event_print *= 10

            self.wave_tree_in.GetEntry(entry)

            for i, wave in enumerate(p_wave):
                # Initialize before each entry
                for j in range(8):
                    cluster_by_radius[i][j][0] = 0
                    dn_dx_by_radius[i][j][0] = 0.0
                dn_dx[i][0] = 0.0
                clusters[i][0] = 0


                peaks = self.cluster_counting_secondDeriv(wave, entry, self._chnls[i], draw)
                if len(peaks)==0:
                    continue  #only count non empty events
                radius = self.find_peak_time_radius(wave,peaks,vth,rt)
                path_length = self.r_to_path_length(radius)

                dndx_val = -1
                if path_length > 0:
                    dndx_val = len(peaks) / path_length * 10  # clusters/cm
                    dn_dx[i][0] = dndx_val  #fill root branch

                radius_bin = -1
                if 0 < radius <= 8:
                    radius_bin = int(radius)
                    if radius_bin < 8 and dndx_val > 0:
                        cluster_by_radius[i][radius_bin][0] = len(peaks) #fill root branch
                        dn_dx_by_radius[i][radius_bin][0] = dndx_val #fill root branch

                clusters[i][0] = len(peaks) #fill root branch

            self.wave_tree_out.Fill()


        p_output_canvas.Close()
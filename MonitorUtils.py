import ROOT
import numpy as np

N_Sipm_Channels = 16

def load_reference_histogram(filename, branch_base_name, bin_edges):
    """Loads data from a reference ROOT file and returns it as histogram counts."""
    ref_fin = ROOT.TFile(filename)
    if not ref_fin or ref_fin.IsZombie():
        print(f"Warning: Could not open reference file {filename}")
        return {}
    
    ref_tree = ref_fin.Get("pulse")
    if not ref_tree:
        print("Warning: 'pulse' tree not found in reference file.")
        ref_fin.Close()
        return {}

    ref_hist_data = {}
    for ch in range(N_Sipm_Channels):
        branch_name = f"{branch_base_name}_ch{ch}"
        data_for_ch = []
        if ref_tree.GetBranch(branch_name):
            ref_tree.SetBranchStatus("*", 0)
            ref_tree.SetBranchStatus(branch_name, 1)
            
            for i in range(ref_tree.GetEntries()):
                ref_tree.GetEntry(i)
                data_for_event = getattr(ref_tree, branch_name)
                if isinstance(data_for_event, (int, float)):
                    # For numbers
                    if data_for_event > 0: 
                        data_for_ch.append(data_for_event)
                else:
                    # For vectors 
                    data_for_ch.extend(list(data_for_event))

        if data_for_ch:
            counts, _ = np.histogram(data_for_ch, bins=bin_edges)
            ref_hist_data[ch] = counts
    
    ref_fin.Close()
    print(f"Successfully loaded reference data for '{branch_base_name}' from {filename}")
    return ref_hist_data
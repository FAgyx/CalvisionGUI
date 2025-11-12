# note: run with python3

import ROOT
import numpy as np
import struct
from array import array
import os
from RTFunction import RTFunction

# Constants
n_channels = 16
n_samples = 1024
trigger_samples = 1024
bytes_per_event = 4 + n_channels * n_samples * 4 + trigger_samples * 4  # 69636

ADC_MAX = 4096
VOLTAGE_RANGE = 1.0
scale_factor = VOLTAGE_RANGE/ADC_MAX

vth_list = [0.004, 0.005, 0.006, 0.007, 0.008]
freq = np.fft.rfftfreq(n_samples, d=1e-9) * 1e-6
index_10mhz = np.argmax(freq > 10)
index_20mhz = np.argmax(freq > 20)

def get_waveform(waveform): 
    waveform_adj = waveform.copy()
    waveform_adj -= np.mean(waveform[:50]) # pedestal subtraction
    return waveform_adj*scale_factor*-1 # returns positive pulse

def get_trigger_waveform(waveform):
    waveform_adj = waveform.copy()
    waveform_adj -= np.abs(np.mean(waveform[:50])) 
    return waveform_adj

def get_trigger_rising_edge(trigger_waveform, vth=-150):
    for i in range(4,trigger_waveform.size):
        if (trigger_waveform[i-4]>vth and 
            trigger_waveform[i-3]<vth and
            trigger_waveform[i-2]<vth and
            trigger_waveform[i-1]<vth):
            return i-3
    return None

def get_waveform_rising_edge(waveform,vth):
    for i in range(4,waveform.size):
        if (waveform[i-4]<vth and 
            waveform[i-3]>vth and
            waveform[i-2]>vth and
            waveform[i-1]>vth):
            return i-3
    return None

def calc_time_diff(trigger_waveform, waveform,vth):
    wf_time = get_waveform_rising_edge(waveform, vth)
    if wf_time is None:
        return None

    trigger_time = get_trigger_rising_edge(trigger_waveform)
    if trigger_time is None:
        return None

    return wf_time - trigger_time

### --- adapted from WaveCluster.py --- ###

def r_to_path_length(r, R=7.1):
    """Calculate chord length for drift radius r in tube of radius R."""
    # r = np.asarray(r)
    if np.any(r > R):
        raise ValueError("Drift radius cannot be larger than tube radius")
    return 2 * np.sqrt(R**2 - r**2) # mm

def find_peak_time_radius(waveform, time_axis, peaks, Vth, rt):
    if not len(peaks):
        return -1

    peak_index = int(peaks[0])
    # max_bin = p_wave_in.GetNbinsX()

    # Step 1: Search backward to find point below threshold
    search_start = peak_index
    while search_start > 0 and waveform[search_start] >= Vth:
        search_start -= 1

    # Step 2: Search forward to find leading edge crossing threshold
    leading_edge_index = -1
    for i in range(search_start, peak_index+1):
        if waveform[i]>Vth:
            leading_edge_index = i
            break
    if leading_edge_index == -1:
        return -1
    # while (leading_edge_index <= peak_index and 
    #         wavefor[leading_edge_index] < Vth):
    #     leading_edge_index += 1
    #     if leading_edge_index > max_bin:
    #         return -1

    # Step 3: Validate and calculate drift time and radius
    drift_time = time_axis[leading_edge_index]
    drift_radius = rt.r(drift_time)
    return drift_radius
    # if leading_edge_index < peak_index:
    #     drift_time = time_axis[leading_edge_index]
    #     drift_radius = rt.r(drift_time)
    #     return drift_radius if drift_radius >= 0 else -1
    # else:
    #     return -1

    
def cluster_counting_secondDeriv(waveform, time_axis):
    y_vals = waveform
    x_vals = time_axis

    # Compute derivatives 
    first_deriv = np.gradient(y_vals, x_vals)
    second_deriv = np.gradient(first_deriv, x_vals) # optional

    # Restrict range
    x_min, x_max = -130, 250
    indices = np.where((x_vals >= x_min) & (x_vals <= x_max))[0]
    if len(indices)==0:
        print("[cluster_counting_secondDeriv] No x vals found")
        return []

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
    return peaks

### ----------------------------------- ###

def read_corrected_dat_file(filename, start_offset):
    filesize = os.path.getsize(filename)
    available_bytes = filesize - start_offset
    n_events = available_bytes // bytes_per_event

    # if there are no new events
    if n_events == 0:
        return [], start_offset, n_events

    with open(filename, "rb") as f:
        f.seek(start_offset)
        raw_data = np.frombuffer(f.read(n_events * bytes_per_event), dtype=np.uint8)

    events = []
    raw_data = raw_data.reshape((n_events, bytes_per_event))

    for ev_data in raw_data:
        offset = 0

        # Event number (int32)
        event_number = struct.unpack("i", ev_data[offset:offset+4])[0]
        offset += 4

        # Channel waveforms (float32)
        ch_data = np.frombuffer(ev_data[offset:offset + n_channels * n_samples * 4], dtype=np.float32).reshape((n_channels, n_samples))
        offset += n_channels * n_samples * 4

        # Trigger waveform
        trig_data = np.frombuffer(ev_data[offset:], dtype=np.float32)

        if ch_data.size != n_channels * n_samples:
            raise ValueError(f"Unexpected channel data size: {ch_data.size}")
        if trig_data.size != trigger_samples:
            raise ValueError(f"Unexpected trigger data size: {trig_data.size}")

        events.append({
            "event": event_number,
            "channels": ch_data,
            "trigger": trig_data
        })

    new_offset = start_offset + n_events * bytes_per_event
    return events, new_offset, n_events


def write_root_file(events, output_filename):
    calibration_file = "autoCalibratedRT_0_100000.root"
    rt = RTFunction(calibration_file)

    f = ROOT.TFile(output_filename, "UPDATE")
    tree = f.Get("pulse")

    # Define the data containers 
    channels_array = array('f', [0.0] * (n_channels * n_samples))
    trigger_array = array('f', [0.0] * trigger_samples)
    event_id = array('i', [0])
    drift_time_vec = [ROOT.std.vector('float')() for _ in range(n_channels)]
    charge_vec = [ROOT.std.vector('float')() for _ in range(n_channels)]
    cluster_count_vec = [array('i', [0]) for _ in range(n_channels)]
    dndx_vec = [array('f', [0.0]) for _ in range(n_channels)]

    if not tree:
        # If the tree doesn't exist, create it and its branches for the first time
        tree = ROOT.TTree("pulse", "Digitizer pulse tree")
        tree.Branch("channels", channels_array, f"channels[{n_channels*n_samples}]/F")
        tree.Branch("trigger", trigger_array, f"trigger[{trigger_samples}]/F")
        tree.Branch("event", event_id, "event/I")
        for i in range(n_channels):
            tree.Branch(f"drift_time_ch{i}", drift_time_vec[i])
            tree.Branch(f"charge_ch{i}", charge_vec[i])
            tree.Branch(f"cluster_count_ch{i}", cluster_count_vec[i], f"cluster_count_ch{i}/I")
            tree.Branch(f"dndx_ch{i}", dndx_vec[i], f"dndx_ch{i}/F")

    else:
        # If the tree exists, connect the arrays to its branches
        tree.SetBranchAddress("channels", channels_array)
        tree.SetBranchAddress("trigger", trigger_array)
        tree.SetBranchAddress("event", event_id)
        for i in range(n_channels):
            tree.SetBranchAddress(f"drift_time_ch{i}", drift_time_vec[i])
            tree.SetBranchAddress(f"charge_ch{i}", charge_vec[i])
            tree.SetBranchAddress(f"cluster_count_ch{i}", cluster_count_vec[i])
            tree.SetBranchAddress(f"dndx_ch{i}", dndx_vec[i])

    # Loop through new events and fill tree
    for evt in events:
        # Flatten the 2D channel data into the 1D array for the TTree branch
        flat_channels = evt["channels"].ravel()

        for i in range(len(flat_channels)):
            channels_array[i] = flat_channels[i]
        for i in range(len(evt["trigger"])):
            trigger_array[i] = evt["trigger"][i]
        event_id[0] = evt["event"]

        for vec in drift_time_vec: vec.clear()
        for vec in charge_vec: vec.clear()

        trigger_processed = get_trigger_waveform(evt["trigger"])

        # create time axis
        trigger_time_index = get_trigger_rising_edge(trigger_processed)
        if trigger_time_index is None:
            print(f"Warning: No trigger found for event {evt['event']}")
            continue
        time_axis = np.arange(n_samples) - trigger_time_index

        for ch in range(n_channels):
            waveform_raw = evt["channels"][ch]
            cluster_count_vec[ch][0] = 0

            # fft signal finding
            fft_mag = np.abs(np.fft.rfft(waveform_raw))
            int_10mhz = np.sum(fft_mag[1:index_10mhz]) # skip 0 MHz (DC component)
            int_20mhz = np.sum(fft_mag[1:index_20mhz]) # skip 0 MHz (DC component)
            if int_10mhz>5000 and int_20mhz>8000: # if it's a signal event
                waveform_processed = get_waveform(waveform_raw)

                # number of clusters
                peaks = cluster_counting_secondDeriv(waveform_processed, time_axis)
                num_clusters = len(peaks)
                cluster_count_vec[ch][0] = num_clusters
                
                # dn/dx
                drift_radius = find_peak_time_radius(waveform_processed, time_axis, peaks, vth_list[0], rt)
                if drift_radius>=0 and num_clusters>0:
                    path_length = r_to_path_length(drift_radius) # mm
                    if path_length>0:
                        path_length /= 10.0 # cm
                        dndx_vec[ch][0] = num_clusters/path_length # clusters/cm

                for vth in vth_list:
                    # time difference (drift time)
                    time_diff = calc_time_diff(trigger_processed,waveform_processed,vth)
                    if time_diff is not None:
                        drift_time_vec[ch].push_back(time_diff)

                    # charge
                    crossing_vth_time = get_waveform_rising_edge(waveform_processed, vth)
                    if crossing_vth_time is not None:
                        end_index = crossing_vth_time + 15 # sum 15 ns after crossing threshold
                        charge = np.abs(np.sum(waveform_processed[crossing_vth_time:end_index]))
                        charge_vec[ch].push_back(charge)
                    
        tree.Fill()

    tree.Write("", ROOT.TObject.kOverwrite)
    f.Close()
    # print(f"[write_root_file] Wrote {len(events)} events to {output_filename}")

def convert_dat_to_monitor_root(dat_file, monitor_root_file, start_offset, total_events_processed):
    events, new_offset, n_new_events = read_corrected_dat_file(dat_file, start_offset)
    
    if not events:
        # print(f'[monitor convert] No new events')
        return new_offset, 0, 0

    sampled_events = []

    for i in range(n_new_events):
        if (total_events_processed+i)%10 == 0:
            # print(f'[monitor convert] Appending event {total_events_processed+i}')
            sampled_events.append(events[i])

    print(f"[monitor convert] Read {n_new_events} new events, sampled {len(sampled_events)} for monitoring")
    
    if sampled_events:
        write_root_file(sampled_events, monitor_root_file)

    return new_offset, len(sampled_events), n_new_events

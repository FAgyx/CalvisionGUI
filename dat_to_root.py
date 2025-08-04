# note: run with python3

import ROOT
import numpy as np
import struct
from array import array

# Constants
n_channels = 16
n_samples = 1024
trigger_samples = 2048
bytes_per_event = 4 + n_channels * n_samples * 4 + trigger_samples * 4  # = 73732


def read_corrected_dat_file(filename):
    events = []

    with open(filename, "rb") as f:
        while True:
            event_data = f.read(bytes_per_event)
            if len(event_data) < bytes_per_event:
                break

            offset = 0

            # Read event number (int32)
            event_number = struct.unpack("i", event_data[offset:offset+4])[0]
            offset += 4

            # Read waveform data (16 channels x 1024 samples = 16384 float32)
            waveform_data = np.frombuffer(event_data[offset:offset + n_channels * n_samples * 4], dtype=np.float32)
            offset += n_channels * n_samples * 4
            waveform_data = waveform_data.reshape((n_channels, n_samples))

            # Read trigger waveform (2048 float32)
            trigger_data = np.frombuffer(event_data[offset:], dtype=np.float32)

            events.append({
                "event": event_number,
                "channels": waveform_data,
                "trigger": trigger_data
            })

    return events

def write_root_file(events, output_filename):
    f = ROOT.TFile(output_filename, "RECREATE")
    tree = ROOT.TTree("pulse", "pulse")

    # Branches
    channels_array = array('f', [0.0] * (n_channels * n_samples))  # 16384 floats
    trigger_array = array('f', [0.0] * trigger_samples)
    event_id = array('i', [0])
    
    tree.Branch("channels", channels_array, f"channels[{n_channels*n_samples}]/F")
    tree.Branch("trigger", trigger_array, f"trigger[{trigger_samples}]/F")
    tree.Branch("event", event_id, "event/I")

    for evt in events:
        np.copyto(np.frombuffer(channels_array, dtype=np.float32), evt["channels"].flatten())
        np.copyto(np.frombuffer(trigger_array, dtype=np.float32), evt["trigger"])
        event_id[0] = evt["event"]
        tree.Fill()

    tree.Write()
    f.Close()

events = read_corrected_dat_file("/hdd/DRS_staging/run_309/outfile_corrected_HG.dat")
write_root_file(events, "outfile_HG.root")
print("Conversion complete: outfile_HG.root")

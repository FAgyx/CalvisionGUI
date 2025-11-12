from PyQt5 import QtCore, QtWidgets
import pyqtgraph as pg
import numpy as np
import struct
from RunConfig import *
import os
import ROOT
import time
from PyQt5.QtCore import QTimer
from dat_to_root import convert_dat_to_monitor_root
from MonitorUtils import load_reference_histogram 

# Set white background and black content for PyQtGraph
pg.setConfigOption('background', 'w')
pg.setConfigOption('foreground', 'k')

N_Sipm_Channels = 16
staging_area = "/hdd/DRS_staging"

class MonitorWorker(QtCore.QThread):
    histograms_ready = QtCore.pyqtSignal(dict)

    def __init__(self, parent_tab, dat_file, last_offset, bin_edges, total_events_processed, last_event_index):
        super().__init__()
        self.parent_tab = parent_tab
        self.dat_file = dat_file
        self.last_offset = last_offset
        self.bin_edges = bin_edges
        self._running = True
        # keeps track of number of sampled events that have be written to monitor.root
        self.last_event_index = last_event_index or {ch: 0 for ch in range(N_Sipm_Channels)} 
        
        # keeps track of total number of events
        self.total_events_processed = total_events_processed 
    
    def run(self):
        if not self._running:
            return
        
        t0 = time.perf_counter()

        # read new data from .dat and convert to .root
        monitor_root_file = self.dat_file.replace('outfile_HG.dat', 'monitor_HG.root')

        try:
            new_offset, n_new_sampled_events, n_new_events = convert_dat_to_monitor_root(
                self.dat_file, 
                monitor_root_file, 
                start_offset=self.last_offset, 
                total_events_processed=self.total_events_processed)
            # print(f'[Monitor] new_offset = {new_offset}, self.last_offset = {self.last_offset}')
        except Exception as e:
            print(f"[DriftMonitor] DAT→ROOT conversion failed: {e}")
            self.histograms_ready.emit({"data": {}, "offset": self.last_offset, "new_event_indices": self.last_event_index, "num_new_events": 0})
            return

        # t1 = time.perf_counter()
        # print(f"[Monitor] convert_dat_to_root took {t1 - t0:.3f} s")

        if n_new_events <= 0:
            print("[DriftMonitor] No new events")
            self.histograms_ready.emit({"data": {}, "offset": self.last_offset, "new_event_indices": self.last_event_index, "num_new_events": 0})
            return

        # opens root file
        fin = ROOT.TFile(monitor_root_file)
        if not fin or fin.IsZombie() or not fin.IsOpen():
            print("[DriftMonitor] Failed to open ROOT file")
            return

        tree = fin.Get("pulse")
        if tree is None:
            print("[DriftMonitor] 'pulse' tree not found")
            fin.Close()
            return

        result = {}
        new_event_indices = {}
        for ch in range(N_Sipm_Channels):
            # print(f"--- Top of the loop for channel {ch} ---") 

            if not self._running:
                print(f'channel {ch} not self._running')
                break

            first_entry = self.last_event_index.get(ch, 0)
            end_point = first_entry + n_new_sampled_events

            # print(f"[Monitor] Processing channel {ch} (first_entry={first_entry}, n_entries={n_new_sampled_events})") # sampled events
            
            # Update last processed event index for this channel
            new_event_indices[ch] = first_entry + n_new_sampled_events

            branch_name = f"drift_time_ch{ch}"
            
            time_diffs_for_ch = []
            if tree.GetBranch(branch_name):
                for i in range(first_entry, end_point):
                    tree.GetEntry(i)
                    time_diffs_for_event = getattr(tree, branch_name)
                    time_diffs_for_ch.extend(list(time_diffs_for_event))
                
                result[ch] = time_diffs_for_ch
            
        # t3 = time.perf_counter()
        # print(f"[DriftMonitor] Loop over channels took {t3 - t2:.3f} s")
        
        fin.Close()

        self.last_offset = new_offset

        if self._running:
            # print(f"[Monitor] Emitting histograms: { {ch: info[-1] for ch, info in result.items()} }, new offset = {new_offset}")
            self.histograms_ready.emit({"data": result, "offset": new_offset, "new_event_indices": new_event_indices, "num_new_events": n_new_events})
        
        t4 = time.perf_counter()
        print(f"[DriftMonitor] Total MonitorWorker.run() time {t4 - t0:.3f} s")

        self.parent_tab.conversion_done.emit(monitor_root_file,n_new_sampled_events)

    def stop(self):
        self._running = False

class tab_drift_monitor(QtCore.QObject):
    conversion_done = QtCore.pyqtSignal(str, int) 
    
    def __init__(self, run_config, status, MainWindow):
        super().__init__()
        self.run_config = run_config
        self.status = status
        
        self.hist_plot_widgets = []
        self.hist_bar_items = []
        self.ref_plot_items = {}
        self.bytes_per_event = 69636
        self.last_offset = 0
        self.last_event_index = {ch: 0 for ch in range(N_Sipm_Channels)}
        self.total_events_processed = 0
        self.worker = None
  
        # Create incremental histograms per channel
        self.bin_edges = np.linspace(-200, 200, 101)  # 100 bins
        self.bin_centers = 0.5 * (self.bin_edges[:-1] + self.bin_edges[1:])
        self.hist_data = {ch: np.zeros(100, dtype=float) for ch in range(N_Sipm_Channels)}
        
        # update plot every 10 seconds
        self.update_timer = QTimer()
        self.update_timer.setInterval(10000)  # 10000 ms = 10 seconds
        self.update_timer.timeout.connect(self.timer_update_plots)
        self.update_timer.start()
        
        ref_file = "/hdd/DRS_staging/run_590/monitor_HG.root"
        self.ref_hist_data = load_reference_histogram(ref_file, "drift_time", self.bin_edges)
       
        self.setup_UI(MainWindow)
        self.is_running = True
        
    def timer_update_plots(self):
        if self.worker is not None and self.worker.isRunning():
            # print("[Main Timer] Worker is still busy. Skipping this cycle.")
            return

        # Only proceed if the worker is not busy and the run is active
        if self.is_running:
            dat_file = os.path.join(staging_area, self.run_config.run_name(), 'outfile_HG.dat')
            if not os.path.exists(dat_file):
                return

            self.worker = MonitorWorker(
                self,
                dat_file, 
                self.last_offset, 
                self.bin_edges, 
                total_events_processed=self.total_events_processed,
                last_event_index=self.last_event_index
            )
            self.worker.histograms_ready.connect(self.on_histograms_ready)
            self.worker.start()

    # incrementally updates existing BarGraphItem and keeps hist_data in memory
    def on_histograms_ready(self, payload):
        self.last_offset = payload["offset"]
        new_event_indices = payload["new_event_indices"]
        self.total_events_processed += payload["num_new_events"]
        result = payload["data"]

        for ch in range(N_Sipm_Channels):
            if ch in result:
                # Get the new data
                data = result[ch]
                
                # Increment the total events for this channel
                self.last_event_index[ch] = new_event_indices[ch]
                
                # Increment the histogram data with new data
                new_counts, _ = np.histogram(data, bins=self.bin_edges)
                self.hist_data[ch] += new_counts
                
                # Now update the plot with the cumulative data
                counts = self.hist_data[ch]
                bin_centers = self.bin_centers
                bin_width = self.bin_edges[1] - self.bin_edges[0]
                
                if self.hist_bar_items[ch] is None:
                    bar = pg.BarGraphItem(x=bin_centers, height=counts, width=bin_width, brush='k')
                    self.hist_bar_items[ch] = bar
                    self.hist_plot_widgets[ch].addItem(bar)
                else:
                    self.hist_bar_items[ch].setOpts(x=bin_centers, height=counts, width=bin_width)
                    
                if len(data) != 0:
                    print(f"[tab_drift_monitor] Channel {ch} updated with {len(data)} new time diffs")
                
                # scale reference hist to live hist
                if ch in self.ref_hist_data:
                    live_peak = np.max(self.hist_data[ch])
                    ref_peak = np.max(self.ref_hist_data[ch])
                    scale_factor = live_peak/ref_peak                    
                    scaled_ref_counts = self.ref_hist_data[ch] * scale_factor
                    self.ref_plot_items[ch].setData(self.bin_edges, scaled_ref_counts)
        
    def run_start(self):
        self.last_offset = 0
        self.is_running = True

    def run_stop(self):
        self.last_offset = 0
        self.is_running = False

    # creates 4x4 grid for 16 PyQtGraph widgets
    def setup_UI(self, MainWindow):
        self.sectionLayout = QtWidgets.QVBoxLayout(MainWindow)
        self.sectionLayout.setSpacing(0)
        self.sectionLayout.setContentsMargins(0, 0, 0, 0)
        MainWindow.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding, QtWidgets.QSizePolicy.MinimumExpanding)

        # Optional container for control buttons
        channelWindow = QtWidgets.QWidget()
        channelWindow.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred)
        channelLayout = QtWidgets.QHBoxLayout(channelWindow)
        self.sectionLayout.addWidget(channelWindow)

        channelEnableWindow = QtWidgets.QWidget()
        enableLayout = QtWidgets.QGridLayout(channelEnableWindow)
        channelLayout.addWidget(channelEnableWindow)

        # 4x4 Grid of per-channel histograms
        self.hist_grid_widget = QtWidgets.QWidget()
        self.hist_grid_layout = QtWidgets.QGridLayout(self.hist_grid_widget)
        self.sectionLayout.addWidget(self.hist_grid_widget)

        for i in range(N_Sipm_Channels):
            plot = pg.PlotWidget()
            plot.setLabel('left', 'Counts')
            plot.setLabel('bottom', 'Drift Time (ns)')
            plot.setTitle(f"Ch {i}", size="10pt")  # Smaller font
            # plot.setYRange(0, 1000)
            plot.setFixedSize(300, 150)

            # reference plots
            if i in self.ref_hist_data:
                ref_counts = self.ref_hist_data[i]
                ref_line = pg.PlotDataItem(
                    self.bin_edges, 
                    ref_counts, 
                    stepMode=True, 
                    pen=pg.mkPen(color=(255, 0, 0, 150), width=2) 
                )
                plot.addItem(ref_line)
                self.ref_plot_items[i] = ref_line

            self.hist_plot_widgets.append(plot)
            self.hist_bar_items.append(None)
            self.hist_grid_layout.addWidget(plot, i // 4, i % 4)
            
    def start_new_run(self):
        # Stop existing worker
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait()

        # Reset offsets and histograms
        self.last_offset = 0
        self.last_event_index = {ch: 0 for ch in range(N_Sipm_Channels)}
        self.total_events_processed = 0
        self.hist_data = {ch: np.zeros(100, dtype=float) for ch in range(N_Sipm_Channels)}

        # Clear plots
        for ch in range(N_Sipm_Channels):
            if self.hist_bar_items[ch]:
                self.hist_plot_widgets[ch].removeItem(self.hist_bar_items[ch])
                self.hist_bar_items[ch] = None
        
        # Reset reference plots
        for ch, plot_item in self.ref_plot_items.items():
            if ch in self.ref_hist_data:
                original_ref_counts = self.ref_hist_data[ch]
                plot_item.setData(self.bin_edges, original_ref_counts)
                
        # print("[tab_drift_monitor] New run initialized")

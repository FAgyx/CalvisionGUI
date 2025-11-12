from PyQt5 import QtCore, QtWidgets
import pyqtgraph as pg
import numpy as np
import struct
from RunConfig import *
import os
import ROOT
import time
from PyQt5.QtCore import QTimer
from MonitorUtils import load_reference_histogram

# Set white background and black content for PyQtGraph
pg.setConfigOption('background', 'w')
pg.setConfigOption('foreground', 'k')

staging_area = "/hdd/DRS_staging"
N_Sipm_Channels = 16

class dndxMonitorWorker(QtCore.QThread):
    histograms_ready = QtCore.pyqtSignal(dict)

    def __init__(self, dat_file, last_event_index, n_new_sampled_events):
        super().__init__()
        self.dat_file = dat_file
        self.last_event_index = last_event_index or {ch: 0 for ch in range(N_Sipm_Channels)} 
        self.n_new_sampled_events = n_new_sampled_events
        self._running = True

    def run(self):
        if not self._running:
            return
        
        t0 = time.perf_counter()

        # read new data from .dat and convert to .root
        monitor_root_file = self.dat_file.replace('outfile_HG.dat', 'monitor_HG.root')
        
        # t1 = time.perf_counter()
        # print(f"[dndxMonitor] convert_dat_to_root took {t1 - t0:.3f} s")

        if self.n_new_sampled_events <= 0:
            print("[dndxMonitor] No new events")
            self.histograms_ready.emit({"data": {}, "new_event_indices": self.last_event_index})
            return

        # opens root file
        fin = ROOT.TFile(monitor_root_file)
        if not fin or fin.IsZombie() or not fin.IsOpen():
            print("[dndxMonitor] Failed to open ROOT file")
            return

        tree = fin.Get("pulse")
        if tree is None:
            print("[dndxMonitor] 'pulse' tree not found")
            fin.Close()
            return

        # t2 = time.perf_counter()
        # print(f"[dndxMonitor] Opening ROOT file took {t2 - t1:.3f} s")

        result = {}
        new_event_indices = {}
        for ch in range(N_Sipm_Channels):
            # print(f"--- Top of the loop for channel {ch} ---") 

            if not self._running:
                print(f'channel {ch} not self._running')
                break

            first_entry = self.last_event_index.get(ch, 0)
            end_point = first_entry + self.n_new_sampled_events

            # print(f"[dndxMonitor] Processing channel {ch} (first_entry={first_entry}, n_entries={n_new_sampled_events})") # sampled events
            
            # Update last processed event index for this channel
            new_event_indices[ch] = end_point

            branch_name = f"dndx_ch{ch}"
            
            dndx_for_ch = []
            if tree.GetBranch(branch_name):
                for i in range(first_entry, end_point):
                    tree.GetEntry(i)
                    dndx_for_event = getattr(tree, branch_name)
                    # print(f"[dndxMonitorWorker] dndx_for_event = {dndx_for_event[0]}")
                    if dndx_for_event > 0:
                        dndx_for_ch.append(dndx_for_event)
                
                result[ch] = dndx_for_ch

        # t3 = time.perf_counter()
        # print(f"[dndxMonitor] Loop over channels took {t3 - t2:.3f} s")
        
        fin.Close()

        if self._running:
            self.histograms_ready.emit({"data": result, "new_event_indices": new_event_indices})
        
        t4 = time.perf_counter()
        print(f"[dndxMonitor] Total dndxMonitorWorker.run() time {t4 - t0:.3f} s")
    
    def stop(self):
        self._running = False

class tab_dndx_monitor(QtCore.QObject):
    def __init__(self, run_config, status, MainWindow):
        super().__init__()
        self.run_config = run_config
        self.status = status
        
        self.hist_plot_widgets = []
        self.hist_bar_items = []
        self.ref_plot_items = {}
        # self.bytes_per_event = 69636
        # self.last_offset = 0
        self.last_event_index = {ch: 0 for ch in range(N_Sipm_Channels)}
        # self.total_events_processed = 0
        self.worker = None
  
        # Create incremental histograms per channel
        self.bin_edges = np.arange(0,11,1)  # 10 bins 
        self.bin_centers = 0.5 * (self.bin_edges[:-1] + self.bin_edges[1:])
        self.hist_data = {ch: np.zeros(10, dtype=float) for ch in range(N_Sipm_Channels)}
        
        ref_file = "/hdd/DRS_staging/run_590/monitor_HG.root"
        self.ref_hist_data = load_reference_histogram(ref_file, "dndx", self.bin_edges)
        
        self.setup_UI(MainWindow)
        self.is_running = True
        
    def start_worker(self, root_filename, n_new_sampled_events):
        """This method is called by the signal from the primary DAQ monitor."""
        if self.worker is not None and self.worker.isRunning():
            return
        if self.is_running:
            dat_file = os.path.join(staging_area, self.run_config.run_name(), 'outfile_HG.dat')
            if not os.path.exists(dat_file): return
            
            # This creates the worker
            self.worker = dndxMonitorWorker(
                dat_file, 
                self.last_event_index,
                n_new_sampled_events,
            )
            self.worker.histograms_ready.connect(self.on_histograms_ready)
            self.worker.start()
    
    # incrementally updates existing BarGraphItem and keeps hist_data in memory   
    def on_histograms_ready(self, payload):
        new_event_indices = payload["new_event_indices"]
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
                    print(f"[on_histograms_ready] Channel {ch} updated with {len(data)} new dN/dX values")
                
                # scale reference hist to live hist
                if ch in self.ref_hist_data: 
                    live_peak = np.max(self.hist_data[ch])
                    ref_peak = np.max(self.ref_hist_data[ch])
                    scale_factor = live_peak/ref_peak                    
                    scaled_ref_counts = self.ref_hist_data[ch] * scale_factor
                    self.ref_plot_items[ch].setData(self.bin_edges, scaled_ref_counts)

    def run_start(self):
        # self.last_offset = 0
        self.is_running = True

    def run_stop(self):
        self.is_running = False
        # self.last_offset = 0

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
            plot.setLabel('bottom', 'clusters/cm')
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
        # self.last_offset = 0
        self.last_event_index = {ch: 0 for ch in range(N_Sipm_Channels)}
        # self.total_events_processed = 0
        self.hist_data = {ch: np.zeros(10, dtype=float) for ch in range(N_Sipm_Channels)}

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

        print("[tab_dndx_monitor] New run initialized")

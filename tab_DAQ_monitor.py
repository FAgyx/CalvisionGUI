from PyQt5 import QtCore, QtWidgets
import pyqtgraph as pg
import numpy as np
import struct
from RunConfig import *

# Set white background and black content for PyQtGraph
pg.setConfigOption('background', 'w')
pg.setConfigOption('foreground', 'k')

N_Sipm_Channels = 16
MCP_Channel = 8
Scint_Channel = 16
N_Channels = 17

class tab_DAQ_monitor(QtCore.QObject):


    def __init__(self, run_config, status, MainWindow):
        super().__init__()
        self.run_config = run_config
        self.status = status
        self.hist_plot_widgets = []
        self.hist_bar_items = []
        self.is_running = False
        # self.bytes_per_event = 4 + 16 * 1024 * 4 + 2048 * 4  # 73732
        self.bytes_per_event = 69636
        self.last_offset = 0

        self.setup_UI(MainWindow)

    def run_start(self):
        self.last_offset = 0
        self.is_running = True

    def run_stop(self):
        self.is_running = False
        self.last_offset = 0

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
            plot.setLabel('bottom', 'TDC')
            plot.setTitle(f"Ch {i}", size="10pt")  # Smaller font
            # plot.setYRange(0, 1000)
            plot.setFixedSize(300, 150)

            self.hist_plot_widgets.append(plot)
            self.hist_bar_items.append(None)
            self.hist_grid_layout.addWidget(plot, i // 4, i % 4)

    def single_plot(self):
        if self.is_running:
            filename = os.path.join(staging_area, self.run_config.run_name(), 'outfile_corrected_HG.dat')
            self.plot_latest_event_waveforms(filename)


    def update_plot(self, waveform_data):
        hg_times, hg_channels = waveform_data
        if hg_channels is not None:
            for i in range(N_Sipm_Channels):
                data = np.array(hg_channels[i])
                hist, bin_edges = np.histogram(data, bins=100, range=(0, 4096))
                bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
                bin_width = bin_edges[1] - bin_edges[0]

                if self.hist_bar_items[i]:
                    self.hist_plot_widgets[i].removeItem(self.hist_bar_items[i])

                bar = pg.BarGraphItem(x=bin_centers, height=hist, width=bin_width, brush='k')
                self.hist_bar_items[i] = bar
                self.hist_plot_widgets[i].addItem(bar)

    def read_new_events_from_dat(self, filename):
        try:
            filesize = os.path.getsize(filename)

            # How many new bytes are available
            available_bytes = filesize - self.last_offset
            new_events = available_bytes // self.bytes_per_event

            if new_events == 0:
                return None  # No new complete events

            with open(filename, "rb") as f:
                f.seek(self.last_offset)

                last_event = None
                printed_events = 0

                for i in range(new_events):
                    event_data = f.read(self.bytes_per_event)
                    if len(event_data) != self.bytes_per_event:
                        print("[read_new_events_from_dat] Unexpected EOF during event read")
                        break

                    offset = 0
                    event_number = struct.unpack("i", event_data[offset:offset+4])[0]
                    offset += 4

                    if printed_events < 10:
                        print(f"[read_new_events_from_dat] Event {i}: number={event_number} at offset={self.last_offset + i * self.bytes_per_event}")
                        printed_events += 1

                    waveform_data = np.frombuffer(
                        event_data[offset:offset + 16 * 1024 * 4],
                        dtype=np.float32
                    ).reshape((16, 1024))
                    offset += 16 * 1024 * 4

                    trigger_data = np.frombuffer(event_data[offset:], dtype=np.float32)

                    last_event = {
                        "event": event_number,
                        "channels": waveform_data,
                        "trigger": trigger_data
                    }
                # self.last_offset += new_events * self.bytes_per_event
                return last_event

        except Exception as e:
            print(f"[read_new_events_from_dat] Error: {e}")
            return None

    def plot_latest_event_waveforms(self, filename):
        event = self.read_new_events_from_dat(filename)
        if event is None:
            return

        for i in range(N_Sipm_Channels):
            self.hist_plot_widgets[i].clear()
            x = np.arange(event["channels"].shape[1])
            y = event["channels"][i]
            curve = pg.PlotCurveItem(x, y, pen='k')
            self.hist_plot_widgets[i].addItem(curve)



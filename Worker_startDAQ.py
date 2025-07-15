from PyQt5.QtCore import *
import time
from CallProcess import *
import struct

class Worker_startDAQ(QObject,CallProcess):
    finished = pyqtSignal()

    def __init__(self, run_config):
        super(Worker_startDAQ, self).__init__()
        self.run_config = run_config
        self.pending_plot = False

    def run(self):
        try:
            run_name = self.run_config.run_name()
            hg_config = self.run_config.hg_config_file()
            lg_config = self.run_config.lg_config_file()
            # source_conda = "source /home/uva/miniforge3/etc/profile.d/conda.sh; conda activate calvision;"
            success = CallProcess.run(self, "/home/muonuser/local_install/bin/dual_readout {} {} {}".format(run_name, hg_config, lg_config))
            print("Process closed!" if success else "Process closed with error!")
        except Exception as e:
            print(f"[run error] {e}")
        finally:
            self.finished.emit()  #emit finished no matter what

    def handle_output(self, line):
        print(line)

    def stop(self):
        if self.running():
            try:
                self.message("stop\n")
            except BrokenPipeError:
                print("BrokenPipe when sending 'stop'")
        for _ in range(20):
            QThread.msleep(100)
            if not self.running():
                return

        print("Graceful stop failed, sending SIGTERM...")
        self.terminate_gracefully()

    def single_plot(self):
        if self.pending_plot == False:            
            self.message("sample plot\n")
            self.pending_plot = True  # Set the flag
        hg_times = None
        hg_channels = None
        try:
            # Briefly wait for the files to be created and filled (sleep ~500ms)
            QThread.currentThread().msleep(500)
            hg_times, hg_channels = self.read_dump_file(self.run_config.hg_dump_file())
            # Optionally check if the data is valid before plotting
            if hg_times is not None and hg_channels is not None:
                # update plot logic here
                pass
        except Exception as e:
            print(f"[single_plot error]: {e}")
        finally:
            self.pending_plot = False  # Always release the flag
            # print("pending_plot released")


        return (hg_times, hg_channels)

        # return (hg_times, hg_channels, lg_times, lg_channels)

    def read_dump_file(self, path):
        try:
            fd = os.open(path, os.O_RDONLY)
            with os.fdopen(fd, 'rb') as f:
                # Read 1024 doubles (timestamps)
                raw_times = f.read(8 * 1024)
                if len(raw_times) != 8 * 1024:
                    raise ValueError("Incomplete timestamp data")

                times = [t[0] for t in struct.iter_unpack('@d', raw_times)]

                # Read 10 channels of 1024 floats
                channels = []
                for c in range(17):
                    raw_channel = f.read(4 * 1024)
                    if len(raw_channel) != 4 * 1024:
                        raise ValueError(f"Incomplete data for channel {c}")
                    channel_data = [v[0] for v in struct.iter_unpack('@f', raw_channel)]
                    channels.append(channel_data)

                return (times, channels)

        except Exception as e:
            # print(f"Error reading dump file: {e}")
            return (None, None)

class Reset_DAQ(CallProcess):
    def run(self):
        # source_conda = "source /home/uva/miniforge3/etc/profile.d/conda.sh; conda activate calvision;"
        CallProcess.run(self, "/home/muonuser/local_install/bin/reset_digitizer")

    def handle_output(self, line):
        print(line)

    def execute():
        Reset_DAQ().run()


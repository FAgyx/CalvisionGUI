# CalvisionGUI

DRS configuration, start DAQ and real time display

```bash
git clone https://github.com/FAgyx/CalvisionGUI.git
cd CalvisionGUI
```

## Add USB rules
Connect the CAEN digitizer USB to the linux machine. Add USB rules so the digitizer appears as v1718_* under /dev/.

Modify udev_rules/10-CAEN-USB.rules VendorID and ProductID according to lsusb:
```bash
lsusb
```
Bus 001 Device 018: ID 21e1:0000 CAEN CAEN DT5xxx USB 1.0

Then copy the USB rule file to system:
```bash
sudo cp udev_rules/10-CAEN-USB.rules  /etc/udev/rules.d/.
```
Reload udev Rules:
```bash
sudo udevadm control --reload
sudo udevadm trigger
```
Unplug and plug back the CAEN digitizer USB, and verify:
```bash
ls -l /dev/v1718*  # or whatever node your device uses
```

## Change DAQ start location
Modify CalvisionGUI/Worker_startDAQ.py, line 18:
CallProcess.run(self, "/home/muonuser/local_install/bin/dual_readout {} {} {}".format(run_name, hg_config, lg_config))

## Change data storage location
Modify 3 files to reflect your data storage directory.
CalvisionGUI/MainWindow.py line 37: default_hg_config = "/hdd/DRS_staging/defaults/highgain.cfg"
CalvisionGUI/RunConfig.py line 28: staging_area = '/hdd/DRS_staging'
CalvisionGUI/tab_digitizer_config.py line 137: self.exportPath_textbox.setText("/hdd/DRS_staging/defaults/highgain.cfg")
CalvisionGUI/tab_digitizer_config.py line 160: self.importPath_textbox.setText("/hdd/DRS_staging/defaults/highgain.cfg")

## Running
Entry file: MainWindow_WaveDump_init.py

## Stopping
If the GUI hangs, the CalvisionDAQ should still be running. Don't close the GUI as it may send a SIGKILL to DAQ which may corrupt the output root file. You can stop the DAQ by sending a SIGTERM through the terminal. Find the pid first by:
```bash
ps aux | grep dual_readout
```
then:
```bash
kill -SIGTERM [pid]
```
Then you can manually exit the GUI. Note: When closing the GUI, a SIGTERM will be sent to DAQ if the subprocess is still running. This works when the GUI is not hanging and the data will not be corrupted. But this is not verified when the GUI hangs.
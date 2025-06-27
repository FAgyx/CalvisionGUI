from PyQt5 import QtWidgets, QtCore
from RunConfig import *
from CallProcess import *
import datetime

# class InhibitProcess(CallProcess):
#     def __init__(self):
#         pass
# 
#     def handle_output(self, line):
#         print(line)
# 
#     def execute(on):
#         postfix = "on"
#         if not on:
#             postfix = "off"
#         return InhibitProcess().run("python3 /home/uva/local_install/python/Inhibit_{}.py".format(postfix))


class CalibrateProcess(CallProcess):
    def __init__(self):
        pass

    def handle_output(self, line):
        print(line)

    def execute():
        CalibrateProcess().run("/home/muonuser/local_install/bin/calibrate")


class tab_run_control(QtCore.QObject):

    status_fields = [
        "Local Time",
        "Run Time",
        "Run Status",
    ]

    
    run_config_changed = QtCore.pyqtSignal()
    begin_run = QtCore.pyqtSignal()
    end_run = QtCore.pyqtSignal()
    inhibit_daq = QtCore.pyqtSignal(bool)
    led_enable = QtCore.pyqtSignal(bool)

    def __init__(self, run_config, run_status, MainWindow):
        super().__init__()
        self.run_config = run_config
        self.run_status = run_status
        self.status_values = {}
        for s in tab_run_control.status_fields:
            self.status_values[s] = None

        self.setup_UI(MainWindow)

    def setup_UI(self, MainWindow):
        
        sectionLayout = QtWidgets.QVBoxLayout(MainWindow)

        runSectionLabel = QtWidgets.QLabel()
        runSectionLabel.setText("----- Run Control")
        sectionLayout.addWidget(runSectionLabel)

        runWindow = QtWidgets.QWidget()
        runLayout = QtWidgets.QFormLayout(runWindow)
        sectionLayout.addWidget(runWindow)

        self.config_comboBoxes = {}
        for key in config_options_comboBox:
            self.config_comboBoxes[key] = QtWidgets.QComboBox()
            self.config_comboBoxes[key].addItems(config_options_comboBox[key])
            self.config_comboBoxes[key].setEditable(True)
            self.config_comboBoxes[key].currentTextChanged.connect(self.update_config)
            runLayout.addRow(key, self.config_comboBoxes[key])


        self.config_lineEdits = {}
        for key, default_value in config_options_lineEdit.items():
            line_edit = QtWidgets.QLineEdit()
            line_edit.setText(default_value) 
            line_edit.setPlaceholderText(f"Enter {key.lower()}")
            line_edit.textChanged.connect(self.update_config)
            self.config_lineEdits[key] = line_edit
            runLayout.addRow(key, line_edit)


        self.repeat_warning = QtWidgets.QLabel()
        runLayout.addRow(self.repeat_warning)


        statusSectionLabel = QtWidgets.QLabel()
        statusSectionLabel.setText("----- Run Status")
        sectionLayout.addWidget(statusSectionLabel)

        statusWindow = QtWidgets.QWidget()
        statusWindow.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding, QtWidgets.QSizePolicy.MinimumExpanding)
        statusLayout = QtWidgets.QFormLayout(statusWindow)
        sectionLayout.addWidget(statusWindow)


        self.statusLabels = {}
        for name in tab_run_control.status_fields:
            self.statusLabels[name] = QtWidgets.QLabel()
            statusLayout.addRow(name + ":", self.statusLabels[name])


        runButtonWindow = QtWidgets.QWidget()
        runButtonWindow.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding, QtWidgets.QSizePolicy.Preferred)
        runButtonLayout = QtWidgets.QGridLayout(runButtonWindow)
        runButtonLayout.setVerticalSpacing(0)
        runButtonLayout.setHorizontalSpacing(0)
        sectionLayout.addWidget(runButtonWindow)
        sectionLayout.setAlignment(runButtonWindow, QtCore.Qt.AlignHCenter)

        def format_button(b):
            font = b.font()
            font.setPointSize(16)
            b.setFont(font)
            b.setStyleSheet("padding-left: 25px; padding-right: 25px; padding-top: 8px; padding-bottom: 8px;")

        row = 0
        column = 0
        self.beginRunButton = QtWidgets.QPushButton()
        self.beginRunButton.setText("Begin Run")
        self.beginRunButton.clicked.connect(self.begin_run)
        self.beginRunButton.setEnabled(True)
        format_button(self.beginRunButton)
        runButtonLayout.addWidget(self.beginRunButton, row, column)

        column += 1
        self.endRunButton = QtWidgets.QPushButton()
        self.endRunButton.setText("End Run")
        self.endRunButton.clicked.connect(self.end_run)
        self.endRunButton.setEnabled(False)
        format_button(self.endRunButton)
        runButtonLayout.addWidget(self.endRunButton, row, column)

        row += 1
        column = 0
        self.calibrateDRSButton = QtWidgets.QPushButton()
        self.calibrateDRSButton.setText("Get DRS Calib Table")
        self.calibrateDRSButton.clicked.connect(self.calibrate_DRS)
        self.calibrateDRSButton.setEnabled(True)
        format_button(self.calibrateDRSButton)
        runButtonLayout.addWidget(self.calibrateDRSButton, row, column)

        # row += 1
        # column = 0
        # self.inhibit_off_button = QtWidgets.QPushButton()
        # self.inhibit_off_button.setText("Enable DAQ")
        # self.inhibit_off_button.clicked.connect(lambda: self.inhibit_daq.emit(False))
        # format_button(self.inhibit_off_button)
        # runButtonLayout.addWidget(self.inhibit_off_button, row, column)

        # column += 1
        # self.inhibit_on_button = QtWidgets.QPushButton()
        # self.inhibit_on_button.setText("Disable DAQ")
        # self.inhibit_on_button.clicked.connect(lambda: self.inhibit_daq.emit(True))
        # format_button(self.inhibit_on_button)
        # runButtonLayout.addWidget(self.inhibit_on_button, row, column)

        # row += 1
        # column = 0
        # self.led_on_button = QtWidgets.QPushButton()
        # self.led_on_button.setText("LED on")
        # self.led_on_button.clicked.connect(lambda: self.led_enable.emit(True))
        # format_button(self.led_on_button)
        # runButtonLayout.addWidget(self.led_on_button, row, column)
 
        # column += 1
        # self.led_off_button = QtWidgets.QPushButton()
        # self.led_off_button.setText("LED off")
        # self.led_off_button.clicked.connect(lambda: self.led_enable.emit(False))
        # format_button(self.led_off_button)
        # runButtonLayout.addWidget(self.led_off_button, row, column)

        # Connect signals and slots

        self.run_config_changed.connect(self.update_config)
        self.begin_run.connect(self.begin_run_button)
        self.end_run.connect(self.end_run_button)
        
        
        # Update state

        self.populate_config_ui_from_prevous_run()

        self.run_config_changed.emit()
        self.update_status_all()
        self.enable_holdoff_controls(False, False)
        # self.enable_led_controls(False, False)

    def calibrate_DRS(self):
        CalibrateProcess.execute()

    def begin_run_button(self):
        self.beginRunButton.setEnabled(False)
        self.endRunButton.setEnabled(True)
        self.set_config_editable(False)

    def end_run_button(self):
        self.beginRunButton.setEnabled(True)
        self.endRunButton.setEnabled(False)
        self.set_config_editable(True)

    def set_config_editable(self, enable):
        for box in self.config_comboBoxes:
            self.config_comboBoxes[box].setEnabled(enable)
    
    def enable_holdoff_controls(self, opened, enable):
        if not opened:
            # self.inhibit_on_button.setEnabled(False)
            # self.inhibit_off_button.setEnabled(False)
            self.set_config_editable(True)
        else:
            # self.inhibit_on_button.setEnabled(not enable)
            # self.inhibit_off_button.setEnabled(enable)
            self.set_config_editable(enable)

    # def enable_led_controls(self, opened, enable):
    #     if not opened:
    #         self.led_on_button.setEnabled(False)
    #         self.led_off_button.setEnabled(False)
    #     else:
    #         self.led_on_button.setEnabled(not enable)
    #         self.led_off_button.setEnabled(enable)

    def update_config(self):
        config_values = {}
        for key in self.config_comboBoxes:
            config_values[key] = self.config_comboBoxes[key].currentText()
        for key in self.config_lineEdits:
            config_values[key] = self.config_lineEdits[key].text()
        self.run_config.from_dict(config_values)

    def populate_config_ui_from_prevous_run(self): #reverse of update_config
        previous_runs = RunConfig.find_all()  #load the most recent json file
        if not previous_runs:
            print("No previous runs found. Skipping UI population.")
            return  # or optionally set default values
        previous_run = previous_runs[0]  # safely access first run now
        self.run_config.from_dict(previous_run.to_dict())  # copy values into existing object
        config_dict = self.run_config.to_dict()  # now reflect those values in the UI 
        # Update comboBoxes
        for key, box in self.config_comboBoxes.items():
            value = config_dict.get(key)
            if value is not None:
                index = box.findText(str(value), QtCore.Qt.MatchFixedString)
                if index >= 0:
                    box.setCurrentIndex(index)

        # Update lineEdits
        for key, line in self.config_lineEdits.items():
            value = config_dict.get(key)
            line.setText(str(value) if value is not None else "")



    def update_repeat_warning(self, is_repeated):
        if is_repeated:
            self.repeat_warning.setText("WARNING: Run config already exists in staging area")
            self.repeat_warning.setStyleSheet("QLabel { color : red; }")
        else:
            self.repeat_warning.setText("Run config doesn't exist in staging area yet.")
            self.repeat_warning.setStyleSheet("QLabel { color : black; }")

    def update_status_all(self):
        for key in tab_run_control.status_fields:
            self.update_status(key)

    def update_status(self, key):
        if self.status_values[key] != None:
            self.statusLabels[key].setText(self.status_values[key])



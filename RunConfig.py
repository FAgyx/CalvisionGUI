import os
import sys
import json
from datetime import datetime

gas = [
    "Argon:CO2 93: 7",
    "Argon:CO2 90:10",
    "Argon:CO2 80:20",
    "Argon:CO2 70:30",
    "Helium:Isobutane 90:10",
    "Helium:Isobutane 80:20",
]


config_options_comboBox = {
    'Gas': gas
}

config_options_lineEdit = {
    'Pressure': 'None',
    'High Voltage': 'None',
    'Temperature': 'None',
    'Humidity': 'None',
}


staging_area = '/hdd/DRS_staging'

class RunConfig:
    def __init__(self):
        self.run_number = 0
        self.gas = None
        self.pressure = None
        self.HV = None
        self.temperature = None
        self.humidity = None
        self.datetime = None


    # def new_config():
    #     run_numbers = [int(name[4:]) for name in os.listdir(staging_area) if name.startswith("run_")]
    #     for i in range(len(run_numbers)):
    #         if i not in run_numbers:
    #             config = RunConfig()
    #             config.run_number = i
    #             return config
    #     config = RunConfig()
    #     config.run_number = len(run_numbers)
    #     return config
 
    def make_next_run(self):
        run_numbers = [int(name[4:]) for name in os.listdir(staging_area) if name.startswith("run_")]
        self.run_number = max(run_numbers) + 1 if len(run_numbers) > 0 else 0
        self.datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.save()


    def to_dict(self):
        return {
            'Gas': self.gas,
            'Pressure': self.pressure,
            'High Voltage': self.HV,
            'Temperature': self.temperature,
            'Humidity': self.humidity,
            "Datetime": self.datetime,
        }

    def from_dict(self, d):
        self.gas = d.get('Gas')
        self.pressure = d.get('Pressure')
        self.HV = d.get('High Voltage')
        self.temperature = d.get('Temperature')
        self.humidity = d.get('Humidity')
        self.datetime = d.get("Datetime")

    def open(run_number):
        config = RunConfig()
        config.run_number = run_number
        path = config.get_path()
        if not os.path.exists(path):
            return None

        with open(path, 'r') as infile:
            data = json.load(infile)
            config.from_dict(data)

        return config

    def save(self):
        path = self.get_path()
        run_dir = os.path.dirname(self.get_path())
        if not os.path.exists(run_dir):
            os.makedirs(run_dir, exist_ok = True)
        with open(path, 'w') as out:
            out.write(json.dumps(self.to_dict(), indent=4))
            print(path+' is written')

    def find_all():
        run_numbers = [int(name[4:]) for name in os.listdir(staging_area) if name.startswith("run_")]
        configs = []
        for i in sorted(run_numbers,reverse=True):
            c = RunConfig.open(i)
            if c != None:
                configs.append(c)
        return configs

    def run_name(self):
        return "run_{}".format(self.run_number)
    
    def get_path(self):
        return self.run_directory() + "/config.json"

    def run_directory(self):
        return staging_area + "/" + self.run_name()

    def hg_config_file(self):
        return self.run_directory() + "/hg_config.cfg"

    def lg_config_file(self):
        return self.run_directory() + "/lg_config.cfg"

    def hg_dump_file(self):
        return self.run_directory() + "/dump_HG"

    def lg_dump_file(self):
        return self.run_directory() + "/dump_LG"

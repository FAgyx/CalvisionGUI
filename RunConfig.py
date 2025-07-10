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

    @staticmethod
    def extract_run_number(name):
        """
        Extracts leading digits after 'run_' from a directory or file name.
        Returns an integer or None if invalid.
        """
        if not name.startswith("run_"):
            return None
        number_part = name[4:]
        digits = ""
        for char in number_part:
            if char.isdigit():
                digits += char
            else:
                break
        return int(digits) if digits else None


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
        run_numbers = []
        for name in os.listdir(staging_area):
            run_num = RunConfig.extract_run_number(name)
            if run_num is not None:
                run_numbers.append(run_num)

        self.run_number = max(run_numbers) + 1 if run_numbers else 0
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
        prefix = f"run_{run_number}"
        match_dir = None

        # Search for a directory or file that starts with run_{run_number}
        for name in os.listdir(staging_area):
            if name.startswith(prefix):
                match_dir = os.path.join(staging_area, name)
                # print(match_dir)
                break

        if match_dir is None:
            return None

        config_path = os.path.join(match_dir, "config.json")
        if not os.path.exists(config_path):
            return None

        config = RunConfig()
        config.run_number = run_number

        with open(config_path, 'r') as infile:
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

    @staticmethod
    def find_all():
        run_numbers = []
        for name in os.listdir(staging_area):
            run_num = RunConfig.extract_run_number(name)
            if run_num is not None:
                run_numbers.append(run_num)

        configs = []
        for i in sorted(run_numbers, reverse=True):
            c = RunConfig.open(i)
            if c is not None:
                configs.append(c)
        return configs



    def run_name(self):
        prefix = f"run_{self.run_number}"
        for name in os.listdir(staging_area):
            if name.startswith(prefix):
                return name  # Return the actual folder name with suffix
        return prefix  # Fallback to default format if no match found

    
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

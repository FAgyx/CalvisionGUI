import subprocess
import sys
import os
import signal


# Helper class for calling processes and communicating data between them
# Run can be called multiple times (makes new process internally)
class CallProcess:
    def __init__(self):
        self.proc = None
        self.timeout = None

    # Runs the process and prints the stdout and stderr
    # This is blocking, but you may call message and other methods
    # from other threads while it's running
    def run(self, command):
        try:
            self.proc = subprocess.Popen(command,
                                         stdin = subprocess.PIPE,
                                         stdout = subprocess.PIPE,
                                         stderr = subprocess.PIPE,
                                         shell = True,
                                         text = True)

            self.pid = self.proc.pid  # Store the PID

            # Readout lines from os file handle. Print them by newline like usual
            self.print_lines_from_fd(self.proc.stdout.fileno(), handle=True )
            self.print_lines_from_fd(self.proc.stderr.fileno(), handle=False)
            
            # Wait for the process to end (pipes might close before process stops)
            self.proc.wait(self.timeout)

            # Check return code
            if self.proc.returncode != 0:
                raise Exception("Command Error {}".format(self.proc.returncode))
        except Exception as e:
            print(e)
            return False
        
        return True

    # Check if the process has started and is running
    def running(self):
        if self.proc == None: return False
        return self.proc.poll() == None

    def terminate_gracefully(self):
        if self.running():
            try:
                os.kill(self.proc.pid, signal.SIGTERM)
                print(f"Sent SIGTERM to process {self.proc.pid}")

                # Wait for process to terminate
                self.proc.wait(timeout=10)
                print("Process terminated gracefully")

            except subprocess.TimeoutExpired:
                print("SIGTERM timed out, escalating to SIGKILL...")
                self.terminate_forcefully()
            except Exception as e:
                print(f"SIGTERM failed: {e}")

        self.proc = None  # Release reference

    def terminate_forcefully(self):
        if self.running():
            try:
                os.kill(self.proc.pid, signal.SIGKILL)
                print(f"Sent SIGKILL to process {self.proc.pid}")
                self.proc.wait(timeout=5)
                print("Process killed forcefully")
            except Exception as e:
                print(f"Failed to forcefully kill process: {e}")
        self.proc = None

    def message(self, text):
        # Check if proc is running
        if not self.running():
            print("Process isn't running. Can't send text: {}".format(text))
            return

        try:
            # Send text through stdin
            os.write(self.proc.stdin.fileno(), text.encode('utf-8'))
        except Exception as e:
            print("Failed to send message {} to the process".format(text))


    def print_lines_from_fd(self, fd, handle=True):
        try:
            s = ""
            while True: 
                new_text = os.read(fd, 10).decode('ascii')
                if len(new_text) == 0:
                    for line in s.splitlines():
                        if handle:
                            self.handle_output(line)
                        else:
                            print(line)
                    break

                s += new_text
                lines = s.splitlines()
                if s[-1] != '\n':
                    s = lines[-1]
                    lines.pop()
                else:
                    s = ""
                for line in lines:
                    if handle:
                        self.handle_output(line)
                    else:
                        print(line)
        except Exception as e:
            print("Failed to read lines from process file descriptor: {}".format(fd))


    # Helper function for how to handle output
    def handle_output(self, line):
        pass


from pymodbus.client import ModbusSerialClient
import time
import ipywidgets as widgets
from IPython.display import display
from functools import partial

class MKSMotor:
    def __init__(self, port, baudrate=38400, parity='N', stopbits=1, bytesize=8, timeout=1,
                 unit=1,
                 max_range=500):
        """
        Initialize serial connection
        :param port: Serial port (e.g., /dev/ttyUSB0 or COM3)
        :param baudrate: Baud rate, default is 9600
        :param parity: Parity bit (N-none, E-even, O-odd)
        :param stopbits: Stop bits, default is 1
        :param bytesize: Data bits, default is 8
        :param timeout: Timeout (seconds)
        """
        self.client = ModbusSerialClient(
            port=port,
            baudrate=baudrate,
            parity=parity,
            stopbits=stopbits,
            bytesize=bytesize,
            timeout=timeout
        )
        self.unit = unit
        self.encoder_pos_zero = None
        self.have_go_home = False
        self.max_range = max_range

    def connect(self):
        self.client.connect()

    def go_home(self, time_out=60):
        """
        Execute homing operation
        :param slave: Slave address
        :return: Homing operation result
        """
        self.have_go_home = False
        try:
            # Send homing command
            response = self.client.write_register(0x0091, 1, slave=self.unit)
            if response.isError():
                raise ValueError("Failed to send homing command")

            # Poll homing status
            start_time = start_time = time.time()
            print('in going home')
            time.sleep(1)
            while True:
                time.sleep(0.1)
                # Check elapsed time
                elapsed_time = time.time() - start_time
                if elapsed_time > time_out:
                    raise TimeoutError(f"Homing operation timed out after {time_out} seconds")
                status_response = self.client.read_input_registers(address=0x00F1, count=1, slave=self.unit)
                if status_response.isError():
                    print("Failed to read homing status")
                    continue

                # Check status register value
                status = status_response.registers[0]
                # if int(elapsed_time) % 2 == 0:
                #     print(f"Homing status: {status}")
                if status == 1:  # Status 0 indicates homing completed
                    print(f"Homing status: {status}")
                    break
            time.sleep(1)
            self.have_go_home = True
            self.encoder_pos_zero = self.read_encoder_position()
            # print(self.encoder_pos_zero)
            return "Motor go home success"
        except Exception as e:
            raise RuntimeError(f"Error during homing operation: {e}")

    def emergency_stop(self):
        # Emergency stop operation
        self.client.write_register(0x00F7, 1, slave=self.unit)
        time.sleep(0.1)
        return 'motor emergency stop'

    def run_motor(self, dire, acc, speed):
        # Speed mode
        if not self.have_go_home:
            print('Have not gone home! Go home first')
            return
        values = [dire * 256 + acc, speed]  # List of values to write
        self.client.write_registers(0x00F6, values, slave=self.unit)
        return '#' + str(self.unit) + ' motor is running in direction ' + \
            str(dire) + ' with ' + str(acc) + ' and ' + str(speed)

    def read_physical_position(self):
        # ...
        if self.have_go_home:
            current = self.read_encoder_position()
            # print('current', current)
            # print('self.encoder_pos_zero', self.encoder_pos_zero)
            pos = -(current - self.encoder_pos_zero) / 16384 * 40
            return pos
        else:
            print('Go home first!')

    def read_encoder_position(self, register=0x0031, count=3):
        """
        Read encoder position
        :param slave: Slave address
        :param register: Register address of encoder position
        :param count: Number of registers to read (default is 2)
        :return: Encoder position value
        """
        result = self.client.read_input_registers(address=register, count=count, slave=self.unit)
        if not result.isError():
            # Combine register values into a complete integer based on device specifications
            # print('result.registers', result.registers)
            position = (result.registers[0] << 32) | (result.registers[1] << 16) | result.registers[2]
            if position >= 2 ** 47:
                position -= 2 ** 48

            return position
        else:
            print(f"Read failed: {result}")
            return None

    def close(self):
        self.client.close()

class MotorControlUI:
    def __init__(self, motor):
        """
        MotorControlUI for controlling an MKSMotor instance with interactive widgets.
        """
        self.motor = motor

        self.output_area = widgets.Output()

        # 1. Buttons for connecting, closing, homing, emergency stop
        self.connect_button = widgets.Button(description="Connect")
        self.close_button = widgets.Button(description="Disconnect")
        self.home_button = widgets.Button(description="Go Home")
        self.emergency_stop_button = widgets.Button(description="Emergency Stop")

        # 2. Buttons for Speed Mode and Distance Mode
        self.run_motor_button = widgets.Button(description="Run motor")

        # 3. Parameters for direction, acceleration, speed
        self.dire_input = widgets.IntText(value=0, description="Dir (0/1)")
        self.acc_input  = widgets.IntText(value=255, description="Acc")
        self.speed_input= widgets.IntText(value=5, description="Speed")

        # 4. Button to read physical position, plus label to display result
        self.read_position_button = widgets.Button(description="Read Position")
        self.position_label = widgets.Label(value="Position: --")

        # Assign button callbacks
        self.connect_button.on_click(self.connect_motor)
        self.close_button.on_click(self.close_motor)
        self.home_button.on_click(self.go_home)
        self.emergency_stop_button.on_click(self.emergency_stop)

        self.run_motor_button.on_click(self.set_run_motor)
        self.read_position_button.on_click(self.read_position)

    def log(self, message):
        """Helper function to clear output before printing new messages."""
        with self.output_area:
            self.output_area.clear_output(wait=True)  # Clear previous output
            print(message)  # Print new message

    def connect_motor(self, _):
        try:
            self.motor.connect()
            self.log("Connected to motor")
        except Exception as e:
            self.log(f"Error connecting: {e}")

    def close_motor(self, _):
        try:
            self.motor.close()
            self.log("Connection closed")
        except Exception as e:
            self.log(f"Error closing connection: {e}")

    def go_home(self, _):
        try:
            result = self.motor.go_home()
            self.log(result)
        except Exception as e:
            self.log(f"Error during homing: {e}")

    def emergency_stop(self, _):
        try:
            result = self.motor.emergency_stop()
            self.log(result)
        except Exception as e:
           self.log(f"Error with emergency stop: {e}")

    def set_run_motor(self, _):
        """Run motor continuously in speed mode with current param values."""
        dire = self.dire_input.value
        acc  = self.acc_input.value
        spd  = self.speed_input.value

        try:
            result = self.motor.run_motor(dire, acc, spd)
            self.log(result)
        except Exception as e:
            self.log(f"Error setting speed mode: {e}")

    def read_position(self, _):
        """Reads the physical position from the motor and displays it."""
        try:
            pos = self.motor.read_physical_position()
            self.log(f"Motor position: {pos}")
            self.position_label.value = f"Position: {pos}"
        except Exception as e:
            self.log(f"Error reading position: {e}")

    # -----------------
    # Display everything
    # -----------------
    def display_controls(self):
        """
        Displays the motor control UI in a structured layout.
        """
        # First column: connect, close, home, emergency stop
        col1 = widgets.VBox([
            widgets.HTML("<b>Connect first</b>"),
            self.connect_button,
            widgets.HTML("<b>Disconnect before closing!</b>"),
            self.close_button,
        ])

        # Second column: direction, acceleration, speed + speed mode
        col2 = widgets.VBox([
            widgets.HTML("<b>Control buttons</b>"),
            self.home_button,
            self.emergency_stop_button,
            self.run_motor_button,
            self.read_position_button,
        ])

        # Third column: distance mode controls (distance input, button)
        col3 = widgets.VBox([
            widgets.HTML("<b>Motor parameters & position</b>"),
            self.dire_input,
            self.acc_input,
            self.speed_input,
            widgets.HBox([self.position_label, widgets.HTML(" mm")])
        ])

        layout = widgets.HBox([col1, col2, col3])
        display(layout, self.output_area)


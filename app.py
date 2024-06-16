from flask import Flask, render_template, jsonify, send_file
import ms5837
import tsys01
import datetime
import time
import csv
import threading
import RPi.GPIO as GPIO
import atexit

app = Flask(__name__)
data_file = 'sensor_data.csv'
logging = True
latest_data = {
    'timestamp': '',
    'pressure_mbar': 0.00,
    'pressure_psi': 0.00,
    'temperature_c': 0.00,
    'temperature_f': 0.00,
    'depth_m': 0.00
}

# Initialize sensors with correct I2C bus (usually bus 1)
pressure_sensor = ms5837.MS5837_30BA(bus=1)
temp_sensor = tsys01.TSYS01(bus=1)

# Check if sensors are initialized properly
if not pressure_sensor.init():
    print("Pressure sensor could not be initialized")
    exit(1)

if not temp_sensor.init():
    print("Temperature sensor could not be initialized")
    exit(1)

# Set up GPIO for the LED
LED_PIN = 25
GPIO.setmode(GPIO.BCM)
GPIO.setup(LED_PIN, GPIO.OUT)

def cleanup():
    GPIO.cleanup()

atexit.register(cleanup)

def blink_led():
    while True:
        if logging:
            print("LED ON")
            GPIO.output(LED_PIN, GPIO.HIGH)
            time.sleep(0.2)
            print("LED OFF")
            GPIO.output(LED_PIN, GPIO.LOW)
            time.sleep(2.8)
        else:
            GPIO.output(LED_PIN, GPIO.LOW)
            time.sleep(1)

def log_data():
    global logging, latest_data
    with open(data_file, mode='a', newline='') as file:
        writer = csv.writer(file)
        # Insert a blank row to separate sessions
        writer.writerow([])
        while True:
            if logging:
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                if pressure_sensor.read() and temp_sensor.read():
                    pressure_mbar = round(pressure_sensor.pressure(), 2)  # mbar
                    pressure_psi = round(pressure_sensor.pressure(ms5837.UNITS_psi), 2)  # psi
                    temperature_c = round(temp_sensor.temperature(), 2)  # Celsius
                    temperature_f = round(temp_sensor.temperature(tsys01.UNITS_Farenheit), 2)  # Fahrenheit
                    depth_m = round(pressure_sensor.depth(), 2)  # Depth in meters
                    data = [timestamp, pressure_mbar, pressure_psi, temperature_c, temperature_f, depth_m]
                    latest_data = {
                        'timestamp': timestamp,
                        'pressure_mbar': pressure_mbar,
                        'pressure_psi': pressure_psi,
                        'temperature_c': temperature_c,
                        'temperature_f': temperature_f,
                        'depth_m': depth_m
                    }
                    writer.writerow(data)
                    file.flush()  # Ensure data is written to the file
                    print(f"{timestamp} - Pressure: {pressure_mbar:.2f} mbar, {pressure_psi:.2f} psi | Temperature: {temperature_c:.2f} C, {temperature_f:.2f} F | Depth: {depth_m:.2f} m")
                else:
                    print("Sensor read failed!")
                time.sleep(0.1)

def start_logging_thread():
    thread = threading.Thread(target=log_data)
    thread.start()

def start_led_blink_thread():
    thread = threading.Thread(target=blink_led)
    thread.start()

# Start the logging and LED blink threads immediately
start_logging_thread()
start_led_blink_thread()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/toggle_logging', methods=['POST'])
def toggle_logging():
    global logging
    logging = not logging
    print(f"Logging status: {'started' if logging else 'stopped'}")
    return jsonify({'status': 'started' if logging else 'stopped'})

@app.route('/latest_data')
def latest_data_route():
    return jsonify(latest_data)

@app.route('/download_data')
def download_data():
    return send_file(data_file, as_attachment=True)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=9123)

from flask import Flask, render_template, jsonify, send_file, request
import ms5837
import tsys01
import datetime
import time
import csv
import threading
import RPi.GPIO as GPIO
import os
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
            time.sleep(0.3)
            print("LED OFF")
            GPIO.output(LED_PIN, GPIO.LOW)
            time.sleep(2.7)
        else:
            GPIO.output(LED_PIN, GPIO.LOW)
            time.sleep(1)

def update_data():
    global latest_data
    while True:
        if pressure_sensor.read() and temp_sensor.read():
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            pressure_mbar = round(pressure_sensor.pressure(), 2)  # mbar
            pressure_psi = round(pressure_sensor.pressure(ms5837.UNITS_psi), 2)  # psi
            temperature_c = round(temp_sensor.temperature(), 2)  # Celsius
            temperature_f = round(temp_sensor.temperature(tsys01.UNITS_Farenheit), 2)  # Fahrenheit
            depth_m = round(pressure_sensor.depth(), 2)  # Depth in meters
            latest_data = {
                'timestamp': timestamp,
                'pressure_mbar': pressure_mbar,
                'pressure_psi': pressure_psi,
                'temperature_c': temperature_c,
                'temperature_f': temperature_f,
                'depth_m': depth_m
            }
            time.sleep(0.1)
        else:
            print("Sensor read failed!")
            time.sleep(1)

def log_data():
    global logging, latest_data
    while True:
        if logging:
            with open(data_file, mode='a', newline='') as file:
                writer = csv.writer(file)
                if os.stat(data_file).st_size == 0:
                    writer.writerow(['Timestamp', 'Pressure (mbar)', 'Pressure (psi)', 'Temperature (C)', 'Temperature (F)', 'Depth (m)'])
                writer.writerow([latest_data['timestamp'], latest_data['pressure_mbar'], latest_data['pressure_psi'], latest_data['temperature_c'], latest_data['temperature_f'], latest_data['depth_m']])
                file.flush()  # Ensure data is written to the file
                print(f"{latest_data['timestamp']} - Pressure: {latest_data['pressure_mbar']:.2f} mbar, {latest_data['pressure_psi']:.2f} psi | Temperature: {latest_data['temperature_c']:.2f} C, {latest_data['temperature_f']:.2f} F | Depth: {latest_data['depth_m']:.2f} m")
        time.sleep(0.1)

def start_logging_thread():
    thread = threading.Thread(target=log_data)
    thread.start()

def start_led_blink_thread():
    thread = threading.Thread(target=blink_led)
    thread.start()

def start_data_update_thread():
    thread = threading.Thread(target=update_data)
    thread.start()

# Start the logging, LED blink, and data update threads immediately
start_logging_thread()
start_led_blink_thread()
start_data_update_thread()

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
    if os.path.exists(data_file):
        return send_file(data_file, as_attachment=True)
    else:
        return jsonify({'status': 'not found'})

@app.route('/delete_data', methods=['POST'])
def delete_data():
    if os.path.exists(data_file):
        os.remove(data_file)
        return jsonify({'status': 'deleted'})
    else:
        return jsonify({'status': 'not found'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=9123)

from OpenGL.GL import *
from OpenGL.GLUT import *
from OpenGL.GLU import *
from intensityto import *
from particle import Particle, create_particle
from quantum_process import generate_qubit_data
from realwave import draw_wave
import random
import math
import time
import threading
from files_for_nn.nn import final_nn
import numpy as np

# global intensity
intensity = -1.0

#global
qubits = []
qubit_datas = []
qubit_live= []
counter = 0

# global wave values
amplitude, frequency, phase = 0.0, 0.0, 0.0
amp, freq, pha = 1, 1, 1
start_time = time.time()

# List to store particles
particles = []


def spawn():
    global particles, intensity
    # Create a new particle occasionally for demonstration
    if len(particles) < 100000:
        particles.append(create_particle(intensity))
    intensity += .001
    if intensity >= 1.0:
        intensity = -1.0


def update_wave():
    global amplitude, frequency, phase, amp, freq, pha

    if abs(amplitude) > 1.0:
        amp = -1.0*amp

    if abs(phase) > 1*math.pi:
        pha = -1.0*pha
    if abs(frequency) > 1.0:
        freq = -1.0*freq
    phase += .001*pha
    amplitude += .001*amp
    frequency += .001*freq


def init():
    glEnable(GL_DEPTH_TEST)  # Enable depth testing for 3D rendering
    glClearColor(0.0, 0.0, 0.0, 1.0)  # Set background color to black

    # Set up the projection matrix
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    gluPerspective(45.0, 1.7777, 0.1, 50.0)  # Set up a perspective projection
    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()


def draw():
    global particles, qubits, counter
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)  # Clear color and depth buffers
    glLoadIdentity()
    gluLookAt(0.0, 0.0, 5.0,  # Eye position
              0.0, 0.0, 0.0,  # Look-at position
              0.0, 1.0, 0.0)  # Up vector

    # Update and draw particles, remove dead ones
    particles = [particle for particle in particles if particle.update()]
    for particle in particles:
        particle.draw()

    for index, (qubit, data, live) in enumerate(zip(qubits, qubit_datas, qubit_live)):
        live['amplitude'] += (-data['amplitude']+qubit['amplitude'])/1000
        live['frequency'] += (-data['frequency'] + qubit['frequency']) /1000
        live['phase'] += (-data['phase'] + qubit['phase']) / 1000


        draw_wave(start_time, 2*live['amplitude'], live['frequency']/2, live['phase']/2, intensity)
    #draw_wave(start_time, 0.9*amplitude, 0.9*frequency, 0.9*phase, 0.9*intensity)
    #draw_wave(start_time, 0.8*amplitude, 0.8*frequency, 0.8*phase, 0.8*intensity)


    glFlush()
    glutSwapBuffers()


def update(value):
    global counter
    # get audio output, output the current now, shift array

    # take averages for input layer

    # process intensity in NN, update intensity global val
    features = np.array([
        120.5,  # tempo
        0.032,  # rms
        1500.3,  # spectral_centroid
        0.45,  # zero_crossing_rate
        -23.0, 17.5, 0.2, -12.3, 7.8, -3.4, 2.1, -6.5, 4.3, -1.2, 0.9, 1.5, -2.8, 3.0, -1.1, 5.6, 7.2, -0.5, 8.3
        # MFCCs (20 values)
    ])
    final_nn(features)

    # quantum math

    spawn()  # create particles

    update_wave()  # update waves
    counter += 1

    glutPostRedisplay()
    glutTimerFunc(16, update, 0)


def qubit_thread():
    global qubits, amplitude, frequency, phase, qubit_datas, qubit_live, counter
    while True:
        qubits_temp = generate_qubit_data(amplitude, frequency, phase)
        if(len(qubits) == 0):
            qubit_live = qubits
            qubit_datas = qubits
        qubits = qubits_temp
        counter = 0
        if(len(qubit_datas) == 0):
            qubit_datas = qubits
            qubit_live = qubits
        time.sleep(0.01)  # Update qubits every 100 milliseconds



def main():
    glutInit()
    glutInitDisplayMode(GLUT_DOUBLE | GLUT_RGB | GLUT_DEPTH)
    glutInitWindowSize(1920, 1080)
    glutCreateWindow("Particle System with Lifetime")
    init()
    glutDisplayFunc(draw)
    glutTimerFunc(16, update, 0)


    # Start the qubit data generation thread
    thread = threading.Thread(target=qubit_thread)
    thread.daemon = True  # Ensures the thread exits when the main program ends
    thread.start()

    glutMainLoop()

main()

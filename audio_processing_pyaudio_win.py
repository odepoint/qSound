import numpy as np
import pyaudiowpatch as pyaudio
import time
import librosa
from scipy.fft import fft, fftfreq

# this works at best occasionally, test machine fills buffer with garbage values

SPEED_OF_SOUND = 343

class AudioHandler(object):
    def __init__(self):
        self.p = pyaudio.PyAudio()
        self.FORMAT = pyaudio.paFloat32
        self.CHANNELS, self.DEVICE_INDEX = self.get_audio_device()
        self.RATE = 48000
        self.CHUNK = int(self.RATE * 0.2)  # 100ms
        self.buffer = np.array([], dtype=np.float32)  # Initialize buffer
        self.amplitude = 0.0
        self.frequency = 0.0
        self.phase = 0.0
        self.spectral_centroid = 0.0
        self.rms = 0.0
        self.bpm = 0.0
        self.features: np.ndarray = np.zeros(24)
        # [tempo, rms, spectral_centroid, zero_crossing_rate, mfcc0.. mfcc19]

    def get_audio_device(self):
        return 2, 5 # placeholder for Windows - not important
    
    def start(self):
        self.stream = self.p.open(input_device_index=self.DEVICE_INDEX,  # 1 = MAC 2 = WIN 2CH
                                  format=self.FORMAT,
                                  channels=self.CHANNELS, # WIN 16
                                  rate=self.RATE,
                                  input=True,
                                  output=False,
                                  stream_callback=self.callback,
                                  frames_per_buffer=self.CHUNK,
                                  )

    def stop(self):
        self.stream.close()
        self.p.terminate()

    def callback(self, in_data, frame_count, time_info, flag):

        numpy_array = np.frombuffer(in_data, dtype=np.float32)

        # Convert multi-channel audio to mono by averaging all channels
        numpy_array = numpy_array.reshape(-1, self.CHANNELS).mean(axis=1)

        # Normalize audio buffer data to keep amplitude consistent
        max_amp = np.max(np.abs(numpy_array))
        if max_amp > 0:
            normalized_buffer = numpy_array / max_amp
        else:
            normalized_buffer = numpy_array

        # Append normalized data to buffer
        self.buffer = np.concatenate((self.buffer, normalized_buffer))

        # Limit buffer size to last 10 seconds
        max_buffer_size = self.RATE * 2
        if len(self.buffer) > max_buffer_size:
            self.buffer = self.buffer[-max_buffer_size:]

        # Compute RMS (Root Mean Square)
        rms = np.sqrt(np.mean(self.buffer ** 2))
        self.rms = rms # for retrieval by quantum
        self.features[1] = rms # as abv for array passed to neural

        # Compute zero crossing rate
        zero_crossings = np.where(np.diff(np.sign(self.buffer)))[0]
        zero_crossing_rate = len(zero_crossings) / len(self.buffer)
        self.features[3] = zero_crossing_rate # array for nn

        # Compute amplitude
        self.amplitude = np.max(np.abs(self.buffer[:30]))

        # Compute FFT to find dominant frequency
        fft_values = fft(self.buffer)
        fft_magnitudes = np.abs(fft_values)
        freqs = fftfreq(len(self.buffer), 1 / self.RATE)

        # Get the frequency with the highest magnitude in the positive frequency range
        positive_freqs = freqs[:len(freqs) // 2]
        positive_magnitudes = fft_magnitudes[:len(fft_magnitudes) // 2]
        idx = np.argmax(positive_magnitudes)
        self.frequency = positive_freqs[idx]
        fft_phases = np.angle(fft_values)  # Get phase for each frequency component
        positive_phases = fft_phases[:len(fft_phases) // 2]  # Phase of positive frequencies
        self.phase = positive_phases[idx]  # Phase of the dominant frequency

        # Calculate Spectral Centroid
        spectral_centroid = np.sum(positive_freqs * positive_magnitudes) / np.sum(positive_magnitudes)
        self.spectral_centroid = spectral_centroid #TODO: repeated
        self.features[2] = spectral_centroid

        # Calculate Time Period and Wavelength
        time_period = 1 / self.frequency if self.frequency != 0 else float('inf')
        wavelength = SPEED_OF_SOUND / self.frequency if self.frequency != 0 else float('inf')

        # Estimate beats per minute
        bpm = self.estimate_bpm()
        self.features[0] = bpm; self.bpm = bpm

        # Compute MFCCs
        mfccs = librosa.feature.mfcc(y=numpy_array, sr=self.RATE, n_mfcc=20)
        mfccs_mean = np.mean(mfccs, axis=1)
        self.features[3:23] = mfccs_mean

        return None, pyaudio.paContinue

    def estimate_bpm(self):
        # Parameters for onset detection
        window_size = 1024
        hop_size = 512

        # Compute the energy of each frame
        energy = []
        for i in range(0, len(self.buffer) - window_size, hop_size):
            frame = self.buffer[i:i + window_size]
            frame_energy = np.sum(frame ** 2)
            if frame_energy > 40:
                energy.append(frame_energy)

        # Normalize energy
        energy /= np.max(energy)

        # filter
        
        # Detect peaks in energy
        peaks = []
        threshold = 0.6  # this is OK but 0.8 is a little better?
        for i in range(1, len(energy) - 1):
            if energy[i] > threshold and energy[i] > energy[i - 1] and energy[i] > energy[i + 1]:
                peaks.append(i)

        # Calculate intervals between peaks
        if len(peaks) > 1:
            peak_times = np.array(peaks) * hop_size / self.RATE
            intervals = np.diff(peak_times)
            avg_interval = np.mean(intervals)
            bpm = 60 / avg_interval
        else:
            bpm = 0  # Not enough peaks to estimate BPM

        return bpm
/**
 * SentiCall v3 — AudioWorklet Processor for Real-Time Streaming Audio
 * Resamples input audio to 16 kHz mono Float32 frames and posts them to the Web Worker.
 */

class SentiCallAudioProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.targetSampleRate = 16000;
    this.buffer = [];
    this.chunkSize = 4096; // ~256ms chunk at 16kHz
  }

  process(inputs, outputs, parameters) {
    const input = inputs[0];
    if (!input || input.length === 0) return true;

    const channelData = input[0];
    if (!channelData || channelData.length === 0) return true;

    // Resample if current context sample rate is not 16000
    // Standard audioContext sampleRate is typically 44100 or 48000
    const sourceRate = sampleRate;
    const ratio = sourceRate / this.targetSampleRate;

    if (Math.abs(ratio - 1.0) < 0.01) {
      // Direct 16kHz
      for (let i = 0; i < channelData.length; i++) {
        this.buffer.push(channelData[i]);
      }
    } else {
      // Linear interpolation downsampling to 16kHz
      const outLength = Math.floor(channelData.length / ratio);
      for (let i = 0; i < outLength; i++) {
        const sourceIndex = i * ratio;
        const indexFloor = Math.floor(sourceIndex);
        const frac = sourceIndex - indexFloor;
        const nextIndex = Math.min(indexFloor + 1, channelData.length - 1);
        const sample = (1.0 - frac) * channelData[indexFloor] + frac * channelData[nextIndex];
        this.buffer.push(sample);
      }
    }

    // Flush when buffer reaches chunkSize
    while (this.buffer.length >= this.chunkSize) {
      const chunk = new Float32Array(this.buffer.slice(0, this.chunkSize));
      this.buffer = this.buffer.slice(this.chunkSize);
      this.port.postMessage({
        type: 'audio_chunk',
        audio: chunk
      }, [chunk.buffer]);
    }

    return true;
  }
}

registerProcessor('senticall-audio-processor', SentiCallAudioProcessor);

"""Models a single network tester application to be run on SpiNNaker."""

from functools import wraps

from enum import IntEnum

import random

class NT_CMD(IntEnum):
    """Network Tester command IDs."""
    
    EXIT = 0x00
    SLEEP = 0x01
    BARRIER = 0x02
    SEED = 0x03
    TIMESTEP = 0x04
    RUN = 0x05
    NUM = 0x06
    
    RECORD = 0x10
    RECORD_INTERVAL = 0x11
    
    PROBABILITY = 0x20
    BURST_PERIOD = 0x21
    BURST_DUTY = 0x22
    BURST_PHASE = 0x23
    SOURCE_KEY = 0x24
    PAYLOAD = 0x25
    NO_PAYLOAD = 0x26
    
    CONSUME = 0x30
    NO_CONSUME = 0x31
    SINK_KEY = 0x32


class RecordBits(IntEnum):
    """The recordable values and their associated bit in NT_CMD_RECORD."""
    local_multicast = 1 << 0
    external_multicast = 1 << 1
    local_p2p = 1 << 2
    external_p2p = 1 << 3
    local_nearest_neighbour = 1 << 4
    external_nearest_neighbour = 1 << 5
    local_fixed_route = 1 << 6
    external_fixed_route = 1 << 7
    dropped_multicast = 1 << 8
    dropped_p2p = 1 << 9
    dropped_nearest_neighbour = 1 << 10
    dropped_fixed_route = 1 << 11
    counter12 = 1 << 12
    counter13 = 1 << 13
    counter14 = 1 << 14
    counter15 = 1 << 15
    
    sent = 1 << 16
    blocked = 1 << 17
    
    received = 1 << 24


class Application(object):
    """A network tester application to run on SpiNNaker."""
    
    def __init__(self):
        # The sequence of commands to be executed by this application
        self._commands = []
        
        self._exited = False
        
        # Was the seed last set using a randomly generated seed?
        self._seeded = False
        
        # What is the current timestep in seconds
        self._current_timestep = None
        
        # The current recording interval in seconds (if 0, record only at start
        # and end).
        self._current_record_interval = 0.0
        
        # The current number of sources and sinks
        self._num_sources = None
        self._num_sinks = None
        
        # What is currently being recorded?
        self._currently_recorded = 0
        
        # A list of probabilities, one for each source.
        self._probability = None
        
        # A list of keys, one for each source
        self._source_key = None
        
        # A list of keys, one for each sink
        self._sink_key = None
        
        # A list of bools indicating whether a payload should be included with
        # generated packets, one for each source
        self._payload = None
        
        # A bool indicating whether packets should be consumed or not
        self._consume = True
        
        # The current burst parameters
        self._current_burst_period = 0.0
        self._current_burst_duty = 0.0
        self._current_burst_phase = 0.0
    
    
    def exit(self):
        """Terminate the network tester application."""
        assert not self._exited
        self._commands.append(NT_CMD.EXIT)
        self._exited = True
    
    
    def sleep(self, duration):
        """Sleep for the specified number of seconds."""
        assert not self._exited
        # Convert to usec
        duration = int(duration * 1e6)
        self._commands.extend([NT_CMD.SLEEP, duration])
    
    
    def barrier(self):
        """Wait for a sync barrier."""
        assert not self._exited
        self._commands.append(NT_CMD.BARRIER)
    
    
    def seed(self, seed=None):
        """Set the random number generator's seed.
        
        If the seed is None, the random number generator will be fed a Unique
        randomly generated seed unless the generator was last seeded with a
        randomly generated seed in which case the random number generator is
        not reseeded.
        
        If a non-null seed is provided, this seed is used.
        """
        assert not self._exited
        
        if seed is None:
            if not self._seeded:
                seed = random.getrandbits(32)
                self._seeded = True
        else:
            self._seeded = False
        
        if seed is not None:
            self._commands.extend([NT_CMD.SEED, seed])
    
    def timestep(self, timestep):
        """Set the timestep in seconds."""
        assert not self._exited
        
        # Don't bother setting the time step if not changed
        if timestep == self._current_timestep:
            return
        
        self._current_timestep = timestep
        
        # Convert to ns
        timestep = int(timestep * 1e9)
        self._commands.extend([NT_CMD.TIMESTEP, timestep])
        
        # Recalculate all values dependent on the time-step if required.
        record_interval = self._current_record_interval
        if record_interval != 0.0:
            self._current_record_interval = None
            self.record_interval(record_interval)
        
        burst_period = self._current_burst_period
        if burst_period != 0.0:
            self._current_burst_period = -1
            self.burst(burst_period,
                       self._current_burst_duty,
                       self._current_burst_phase)
    
    def run(self, duration):
        """Run the generator for a given number of seconds."""
        assert not self._exited
        # Convert to timesteps (round to soften the blow of floating point
        # precision issues)
        duration = int(round(duration / self._current_timestep))
        self._commands.extend([NT_CMD.RUN, duration])
    
    def num(self, num_sources, num_sinks):
        """Specify the number of sources and sinks.
        
        May only be done once. This is an artificial constraint to simplify
        result collection.
        """
        assert not self._exited
        
        assert self._num_sources is None
        assert self._num_sinks is None
        
        self._num_sources = num_sources
        self._num_sinks = num_sinks
        
        self._probability = [0.0] * num_sources
        self._source_key = [0] * num_sources
        self._payload = [False] * num_sources
        
        self._sink_key = [0] * num_sinks
        
        self._commands.extend([NT_CMD.NUM, num_sources | (num_sinks << 8)])
    
    
    def record(self, **counters):
        """Set the set of counters to record.
        
        Any counter name in :py:class:`.RecordBits` may be specified. If a
        counter is not specified, it is assumed to be disabled.
        """
        assert not self._exited
        
        recorded = 0
        for counter in RecordBits:
            if counters.pop(counter.name, False):
                recorded |= counter
        assert len(counters) == 0
        
        # Only set the recording set if it changes
        if recorded != self._currently_recorded:
            self._currently_recorded = recorded
            self._commands.extend([NT_CMD.RECORD, recorded])
    
    
    def record_interval(self, interval):
        """Set the interval between recording values in seconds. If 0, record
        only the counters at the end of the run.
        
        Any counter name in :py:class:`.RecordBits` may be specified. If a
        counter is not specified, it is assumed to be disabled.
        """
        assert not self._exited
        
        # Don't add the command if not required
        if self._current_record_interval != interval:
            self._current_record_interval = interval
            
            # Convert to ticks
            interval = int(round(interval / self._current_timestep))
            self._commands.extend([NT_CMD.RECORD_INTERVAL, interval])
    
    def probability(self, source_num, probability):
        """Set the generation probability of a particular source."""
        assert not self._exited
        assert source_num < self._num_sources
        
        # Only output if changed
        if self._probability[source_num] != probability:
            self._probability[source_num] = probability
            # Convert to value between 0 and 0xFFFFFFFF
            if probability == 1.0:
                probability = 0xFFFFFFFF
            else:
                probability = int(round(probability * (1 << 32)))
            self._commands.extend([NT_CMD.PROBABILITY | (source_num << 8),
                                   probability])
    
    def burst(self, period, duty, phase=0.0):
        """Set the bursting behaviour of the generator.
        
        Parameters
        ----------
        period : float
            The number of seconds the bursting cycle period lasts.
        duty : float
            The proportion of the duty cycle to generate packets.
        phase : float or None
            The proportion of the way through the duty cycle the burst
            generator should start at. If None, this is set randomly.
        """
        assert not self._exited
        
        # Don't add the commands only when required
        if self._current_burst_period != period:
            self._current_burst_period = period
            
            # Force recomputation of these values
            self._current_burst_duty = -1
            self._current_burst_phase = -1
            
            # Convert to ticks
            period_ = int(round(period / self._current_timestep))
            self._commands.extend([NT_CMD.BURST_PERIOD, period_])
        
        # No other options are relevant when the period is set to 0 (i.e.
        # disabled)
        if period == 0:
            return
        
        if self._current_burst_duty != duty:
            self._current_burst_duty = duty
            
            # Convert to ticks
            duty = int(round((period * duty) / self._current_timestep))
            self._commands.extend([NT_CMD.BURST_DUTY, duty])
        
        if self._current_burst_phase != phase:
            # Generate a random phase if requested (setting the current value
            # such that it will always be replaced)
            if phase is None:
                phase = random.random()
                self._current_burst_phase = -1
            else:
                self._current_burst_phase = phase
            
            # Convert to ticks
            phase = int(round((period * phase) / self._current_timestep))
            self._commands.extend([NT_CMD.BURST_PHASE, phase])
    
    def source_key(self, source_num, key):
        """Set the top 24-bits of the key for a traffic source."""
        assert not self._exited
        assert source_num < self._num_sources
        
        # Only output if changed
        key &= ~0xFF
        if self._source_key[source_num] != key:
            self._source_key[source_num] = key
            self._commands.extend([NT_CMD.SOURCE_KEY | (source_num << 8), key])
    
    def payload(self, source_num, payload):
        """Set the top 24-bits of the key for a traffic source."""
        assert not self._exited
        assert source_num < self._num_sources
        
        # Only output if changed
        if self._payload[source_num] != payload:
            self._payload[source_num] = payload
            self._commands.append((NT_CMD.PAYLOAD if payload else 
                                   NT_CMD.NO_PAYLOAD) | (source_num << 8))
    
    def consume(self, consume):
        """Select whether packets are consumed or left in the network."""
        assert not self._exited
        
        # Only output if changed
        if self._consume != consume:
            self._consume = consume
            self._commands.append(NT_CMD.CONSUME if consume else 
                                  NT_CMD.NO_CONSUME)
    
    def sink_key(self, sink_num, key):
        """Set the top 24-bits of the key for a traffic source."""
        assert not self._exited
        assert sink_num < self._num_sinks
        
        # Only output if changed
        key &= ~0xFF
        if self._sink_key[sink_num] != key:
            self._sink_key[sink_num] = key
            self._commands.extend([NT_CMD.SINK_KEY | (sink_num << 8), key])
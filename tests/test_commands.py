import pytest

from six import integer_types

from mock import Mock

from network_tester.commands import NT_CMD, Commands

from network_tester.counters import Counters


def test_exited_only_once():
    # Exiting the application should prevent any further commands being added.
    a = Commands()
    
    a.exit()
    assert a._commands == [NT_CMD.EXIT]
    
    with pytest.raises(Exception):
        a.exit()


def test_sleep():
    # Make sure unit conversions work out correctly
    a = Commands()
    a.sleep(0.000001)
    assert a._commands == [NT_CMD.SLEEP, 1]


def test_barrier():
    # Make sure barriers are added
    a = Commands()
    a.barrier()
    assert a._commands == [NT_CMD.BARRIER]


def test_seed():
    # Make sure seeding works as expected
    a = Commands()
    
    # Should be able to seed automatically
    a.seed()
    assert len(a._commands) == 2
    assert a._commands[0] == NT_CMD.SEED
    assert isinstance(a._commands[1], integer_types)
    
    # Reseeding shouldn't change the seed (as there's no point)
    a.seed()
    assert len(a._commands) == 2
    
    # Setting the seed to a custom value should work
    a.seed(123)
    assert len(a._commands) == 4
    assert a._commands[-2:] == [NT_CMD.SEED, 123]
    
    # Setting the seed to a custom value should set the seed even if the value
    # doesn't change
    a.seed(123)
    assert len(a._commands) == 6
    assert a._commands[-2:] == [NT_CMD.SEED, 123]
    
    # Setting the seed to a None again should reseed
    a.seed()
    assert len(a._commands) == 8
    assert a._commands[-2] == NT_CMD.SEED
    assert isinstance(a._commands[-1], integer_types)
    
    # And reseeding again now shouldn't do anything again
    a.seed()
    assert len(a._commands) == 8


def test_timestep():
    # Make sure setting the timestep works correctly
    a = Commands()
    a.timestep(1e-9)
    assert a._commands == [NT_CMD.TIMESTEP, 1]
    
    # If we change it to the same thing, it shouldn't get set again
    a.timestep(1e-9)
    assert len(a._commands) == 2
    
    # If we change it to something different, it should get set again
    a.timestep(1e-6)
    assert len(a._commands) == 4
    assert a._commands[2:] == [NT_CMD.TIMESTEP, 1000]


def test_run():
    # Make sure running converts from seconds correctly
    a = Commands()
    a.timestep(1e-9)
    a.run(1e-6)
    assert a._commands[2:] == [NT_CMD.RUN, 1000]


def test_num():
    # Make sure setting number of sources and sinks works correctly
    a = Commands()
    a.num(0xAA, 0xBB)
    assert a._commands == [NT_CMD.NUM, 0xBBAA]
    
    # Should not be able to change
    with pytest.raises(Exception):
        a.num(1, 1)


def test_record():
    # Make sure setting recorded counters works
    a = Commands()
    
    # Should be able to set nothing to be recorded without a new command being
    # added.
    a.record()
    assert a._commands == []

    # Should be able to set multiple things
    a.record(Counters.local_multicast, Counters.sent)
    assert a._commands == [NT_CMD.RECORD, (1 << 0) | (1 << 16)]

    # Doing the same again shouldn't add a new command
    a.record(Counters.local_multicast, Counters.sent)
    assert len(a._commands) == 2


def test_record_interval():
    # Make sure the record interval is converted correctly and is updated when
    # the timestep changes.
    a = Commands()
    
    a.timestep(1e-9)
    assert len(a._commands) == 2
    
    # No change
    a.record_interval(0)
    assert len(a._commands) == 2
    
    # Should get set on change
    a.record_interval(1e-6)
    assert len(a._commands) == 4
    assert a._commands[-2:] == [NT_CMD.RECORD_INTERVAL, 1000]
    
    a.record_interval(1e-3)
    assert len(a._commands) == 6
    assert a._commands[-2:] == [NT_CMD.RECORD_INTERVAL, 1000000]
    
    # Should not get set when the same
    a.record_interval(1e-3)
    assert len(a._commands) == 6
    
    # Should get changed when the timestep changes
    a.timestep(1e-6)
    assert len(a._commands) == 10
    assert a._commands[-2:] == [NT_CMD.RECORD_INTERVAL, 1000]


def test_probability():
    # Make sure the probability can be changed.
    a = Commands()
    
    a.num(2, 0)
    assert len(a._commands) == 2
    
    # If not changed, shouldn't produce any commands
    a.probability(0, 0.0)
    a.probability(1, 0.0)
    assert len(a._commands) == 2
    
    # If should produce command on change
    a.probability(0, 0.5)
    assert len(a._commands) == 4
    assert a._commands[-2:] == [NT_CMD.PROBABILITY | (0 << 8),
                                1<<31]
    a.probability(1, 0.25)
    assert len(a._commands) == 6
    assert a._commands[-2:] == [NT_CMD.PROBABILITY | (1 << 8),
                                1<<30]
    
    # No command should be produced on non-change again
    a.probability(0, 0.5)
    a.probability(1, 0.25)
    assert len(a._commands) == 6
    
    # Extremes should work
    a.probability(0, 0.0)
    assert len(a._commands) == 8
    assert a._commands[-2:] == [NT_CMD.PROBABILITY | (0 << 8), 0]
    a.probability(1, 1.0)
    assert len(a._commands) == 10
    assert a._commands[-2:] == [NT_CMD.PROBABILITY | (1 << 8), 0xFFFFFFFF]


def test_burst():
    # Make sure the burst mode can be changed (and that it is changed by
    # changing the timestep.
    a = Commands()
    
    a.timestep(1e-9)
    assert len(a._commands) == 2
    
    # Shouldn't change if leaving it at the default (disabled)
    a.burst(0.0, 0.0, 0.0)
    a.burst(0.0, 123.0, None)
    assert len(a._commands) == 2
    
    # Should change everything when the period changes
    a.burst(1e-6, 0.1, 0.1)
    assert len(a._commands) == 8
    assert a._commands[-6:] == [NT_CMD.BURST_PERIOD, 1000,
                                NT_CMD.BURST_DUTY, 100,
                                NT_CMD.BURST_PHASE, 100]
    
    # Should change everything when the period changes
    a.burst(2e-6, 0.1, 0.1)
    assert len(a._commands) == 14
    assert a._commands[-6:] == [NT_CMD.BURST_PERIOD, 2000,
                                NT_CMD.BURST_DUTY, 200,
                                NT_CMD.BURST_PHASE, 200]
    
    # Should change nothing if nothing changes
    a.burst(2e-6, 0.1, 0.1)
    assert len(a._commands) == 14
    
    # Should just change other parts when only they change
    a.burst(2e-6, 0.1, 0.5)
    assert len(a._commands) == 16
    assert a._commands[-2:] == [NT_CMD.BURST_PHASE, 1000]
    
    a.burst(2e-6, 0.2, 0.5)
    assert len(a._commands) == 18
    assert a._commands[-2:] == [NT_CMD.BURST_DUTY, 400]
    
    # Should change everything when timestep changed
    a.timestep(2e-9)
    assert len(a._commands) == 26
    assert a._commands[-6:] == [NT_CMD.BURST_PERIOD, 1000,
                                NT_CMD.BURST_DUTY, 200,
                                NT_CMD.BURST_PHASE, 500]
    
    # Should change phase when randomized
    a.burst(2e-6, 0.2, None)
    assert len(a._commands) == 28
    assert a._commands[-2] == NT_CMD.BURST_PHASE
    
    a.burst(2e-6, 0.2, None)
    assert len(a._commands) == 30
    assert a._commands[-2] == NT_CMD.BURST_PHASE


def test_source_key():
    # Make sure the source key can be changed.
    a = Commands()
    
    a.num(2, 0)
    assert len(a._commands) == 2
    
    # If not changed, shouldn't produce any commands
    a.source_key(0, 0)
    a.source_key(1, 0)
    assert len(a._commands) == 2
    
    # If should produce command on change (and should mask off bottom bits)
    a.source_key(0, 0x00BEEFAA)
    assert len(a._commands) == 4
    assert a._commands[-2:] == [NT_CMD.SOURCE_KEY | (0 << 8),
                                0x00BEEF00]
    a.source_key(1, 0x00DEADBB)
    assert len(a._commands) == 6
    assert a._commands[-2:] == [NT_CMD.SOURCE_KEY | (1 << 8),
                                0x00DEAD00]
    
    # No command should be produced on non-change again (note just the
    # masked-off bits are different)
    a.source_key(0, 0x00BEEFCC)
    a.source_key(1, 0x00DEADDD)
    assert len(a._commands) == 6


def test_payload():
    # Make sure the payload can be changed.
    a = Commands()
    
    a.num(2, 0)
    assert len(a._commands) == 2
    
    # If not changed, shouldn't produce any commands
    a.payload(0, False)
    a.payload(1, False)
    assert len(a._commands) == 2
    
    # Should produce a command when changed
    a.payload(0, True)
    assert len(a._commands) == 3
    assert a._commands[-1] == NT_CMD.PAYLOAD | (0 << 8)
    a.payload(1, True)
    assert len(a._commands) == 4
    assert a._commands[-1] == NT_CMD.PAYLOAD | (1 << 8)
    
    # No command should be produced on another non-change
    a.payload(0, True)
    a.payload(1, True)
    assert len(a._commands) == 4
    
    # Should produce a command when changed back
    a.payload(0, False)
    assert len(a._commands) == 5
    assert a._commands[-1] == NT_CMD.NO_PAYLOAD | (0 << 8)
    a.payload(1, False)
    assert len(a._commands) == 6
    assert a._commands[-1] == NT_CMD.NO_PAYLOAD | (1 << 8)


def test_consume():
    # Make sure the consumption mode can be changed.
    a = Commands()
    
    # If not changed, shouldn't produce any commands
    a.consume(True)
    assert len(a._commands) == 0
    
    # Should produce a command on change
    a.consume(False)
    assert len(a._commands) == 1
    assert a._commands[-1] == NT_CMD.NO_CONSUME
    
    # If not changed, shouldn't produce any commands
    a.consume(False)
    assert len(a._commands) == 1
    
    # Should produce a command on change
    a.consume(True)
    assert len(a._commands) == 2
    assert a._commands[-1] == NT_CMD.CONSUME


def test_sink_key():
    # Make sure the source key can be changed.
    a = Commands()
    
    a.num(0, 2)
    assert len(a._commands) == 2
    
    # If not changed, shouldn't produce any commands
    a.sink_key(0, 0)
    a.sink_key(1, 0)
    assert len(a._commands) == 2
    
    # If should produce command on change (and should mask off bottom bits)
    a.sink_key(0, 0x00BEEFAA)
    assert len(a._commands) == 4
    assert a._commands[-2:] == [NT_CMD.SINK_KEY | (0 << 8),
                                0x00BEEF00]
    a.sink_key(1, 0x00DEADBB)
    assert len(a._commands) == 6
    assert a._commands[-2:] == [NT_CMD.SINK_KEY | (1 << 8),
                                0x00DEAD00]
    
    # No command should be produced on non-change again (note just the
    # masked-off bits are different)
    a.sink_key(0, 0x00BEEFCC)
    a.sink_key(1, 0x00DEADDD)
    assert len(a._commands) == 6


def test_size():
    # Size should report correctly (including a prefix giving the length
    a = Commands()
    a.num(0, 0)
    a.exit()
    
    assert len(a._commands) == 3
    
    assert a.size == 16


def test_pack():
    # Packing should work correctly
    a = Commands()
    a.num(0, 0)
    a.exit()
    
    assert len(a._commands) == 3
    
    assert a.pack() == (b"\x0C\0\0\0"  # 12 bytes of commands
                        b"\x06\0\0\0"b"\0\0\0\0"  # NT_CMD_NUM
                        b"\x00\0\0\0")  # NT_CMD_EXIT
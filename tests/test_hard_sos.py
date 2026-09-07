import pytest
from src.agents.hard_sos import HardSosEngine

CRITICAL_INCIDENTS = [
    "Car collision on GST Road. The driver is unconscious and not breathing.",
    "Bike accident, rider is bleeding heavily from head and unresponsive.",
    "Pedestrian hit by bus, trapped under truck with severe bleeding.",
    "Elderly man collapsed at bus stop, no pulse, bystander starting CPR.",
    "Highway accident, passenger is gasping for air and soaked in blood.",
]

BORDERLINE_FALSE_POSITIVE_BIAS_CASES = [
    "Rider fell off scooter. He seemed to have passed out for a second but is sitting now.",
    "Minor scrape on leg but caller says driver fainted from panic.",
    "Cut on palm from broken windshield, lots of bleeding heavily described by panicking bystander.",
]

BENIGN_INCIDENTS = [
    "Motorcycle skidded on wet road. Driver has minor bruises on elbow and knee, fully conscious.",
    "Car bumped into divider, passenger complaining of mild neck stiffness and wrist pain.",
    "Sprained ankle after slipping on road edge, patient alert and talking.",
]

def test_hard_sos_critical_detection():
    for text in CRITICAL_INCIDENTS:
        is_sos, triggers, rationale, latency = HardSosEngine.evaluate(text)
        assert is_sos is True, f"Failed to detect hard SOS for: '{text}'"
        assert len(triggers) > 0
        assert latency < 10.0, f"Latency {latency}ms exceeded 10ms threshold"

def test_hard_sos_false_positive_bias():
    for text in BORDERLINE_FALSE_POSITIVE_BIAS_CASES:
        is_sos, triggers, rationale, latency = HardSosEngine.evaluate(text)
        assert is_sos is True, f"Expected safety-first false-positive trigger on borderline case: '{text}'"

def test_hard_sos_benign_cases():
    for text in BENIGN_INCIDENTS:
        is_sos, triggers, rationale, latency = HardSosEngine.evaluate(text)
        assert is_sos is False, f"False positive on completely benign report: '{text}'"
        assert len(triggers) == 0

def test_sub_millisecond_benchmark():
    sample = "Two wheeler crash on OMR, victim unresponsive and bleeding heavily."
    times = []
    for _ in range(100):
        _, _, _, lat = HardSosEngine.evaluate(sample)
        times.append(lat)
    avg_latency = sum(times) / len(times)
    assert avg_latency < 1.0, f"Average latency {avg_latency}ms must be sub-millisecond"

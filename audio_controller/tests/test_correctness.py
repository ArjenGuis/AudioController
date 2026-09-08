from audio_controller import controller


def test_config_has_url_in():
    # C1: config.url_in must exist (was referenced in scan_ports but never assigned)
    assert hasattr(controller.config, "url_in")
    assert controller.config.url_in is None


def test_stop_all_clears_url_in():
    # C1: after stopping everything, url_in is cleared.
    # stop_all() is opgesplitst in plannen (geen I/O) en uitvoeren, zodat de seriele
    # opdrachten naar de ITEC-thread kunnen; de invariant blijft dezelfde.
    controller.config.url_in = "http://example/live"
    controller.config.sources = []
    routes, url_in, urls_out = controller.config.plan_sources_destinations([], [])
    assert (url_in, urls_out) == (None, [])
    # url_in wordt al bij het plannen gewist, voor de await naar de ITEC-thread,
    # zodat scan_ports er niet nog een ronde de vorige stream mee meet
    assert controller.config.url_in is None

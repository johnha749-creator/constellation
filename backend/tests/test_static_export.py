import json

from app.static_export import main


def test_export_writes_every_response_for_both_states(tmp_path):
    main(str(tmp_path))
    read = lambda *parts: json.loads(tmp_path.joinpath(*parts).read_text(encoding="utf-8"))  # noqa: E731

    assert read("rubric.json")["link_at"] == 4.2
    base, polaris = read("base", "stats.json"), read("polaris", "stats.json")
    assert (base["hospitals"], base["patients"]) == (3, 25)
    assert (polaris["hospitals"], polaris["patients"]) == (4, 26)
    assert read("polaris", "report.json")["new_conflicts"][0]["patient"] == "Kenji Murphy"

    for state in ("base", "polaris"):
        for patient in read(state, "patients.json"):
            for name in ("constellation", "medications", "audit"):
                assert tmp_path.joinpath(state, "patients", patient["id"], f"{name}.json").exists()
    # Contact details stay masked in the hosted demo, as for a signed-in clinician.
    maria = next(p for p in read("base", "patients.json") if p["name"] == "Maria Gonzalez")
    assert read("base", "patients", maria["id"], "constellation.json")["contact_details_visible"] is False

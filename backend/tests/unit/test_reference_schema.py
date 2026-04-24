from app.domain.schemas.reference import ReferenceCandidateRead, ReferenceOrigin


def test_reference_candidate_accepts_extended_metadata():
    item = ReferenceCandidateRead(
        id="scene:scene01",
        kind="scene",
        source_id="scene01",
        name="长安殿",
        alias="长安殿",
        mention_key="scene:scene01",
        image_url="https://static.example.com/scene.png",
        origin=ReferenceOrigin.AUTO,
        reason="镜头已绑定该场景",
    )

    assert item.alias == "长安殿"
    assert item.mention_key == "scene:scene01"
    assert item.origin == "auto"

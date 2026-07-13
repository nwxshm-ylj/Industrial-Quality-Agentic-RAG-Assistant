from app.rag.index_activation import activate_validated_vector_alias


class _VectorBackend:
    def __init__(self, count: int) -> None:
        self.count = count
        self.activated = False

    def count_indexed(self) -> int:
        return self.count

    def activate_alias(self) -> None:
        self.activated = True


class _KeywordBackend:
    def __init__(self, count: int) -> None:
        self.count = count

    def count_indexed(self) -> int:
        return self.count


def main() -> None:
    vector = _VectorBackend(5)
    keyword = _KeywordBackend(5)
    result = activate_validated_vector_alias(vector, keyword)
    assert vector.activated is True
    assert result["vector_count"] == 5

    mismatch_vector = _VectorBackend(5)
    try:
        activate_validated_vector_alias(
            mismatch_vector,
            _KeywordBackend(4),
        )
    except RuntimeError as exc:
        assert "counts differ" in str(exc)
    else:
        raise AssertionError("count mismatch must block alias activation")
    assert mismatch_vector.activated is False

    empty_vector = _VectorBackend(0)
    try:
        activate_validated_vector_alias(empty_vector, _KeywordBackend(0))
    except RuntimeError as exc:
        assert "empty vector index" in str(exc)
    else:
        raise AssertionError("empty indexes must block alias activation")
    assert empty_vector.activated is False
    print("Index activation guard tests passed")


if __name__ == "__main__":
    main()

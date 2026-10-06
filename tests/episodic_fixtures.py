from galet_memory import NewEvent, Event, EventPage

def event_fixture(role, content, actor='fixture', **kwargs):
    cls = Event if any(k in kwargs for k in ('event_id', 'sequence', 'stored_at', 'session_id')) else NewEvent
    return cls(role=role, content=content, actor=actor, **kwargs)

def memory_fixture(*, events=(), **kwargs):
    return EventPage(tuple(events))

class EmptyEpisodic:
    def search_digests(self, **kwargs):
        return []

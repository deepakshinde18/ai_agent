from fastapi import Request


def get_graph(request: Request):
    return request.app.state.graph

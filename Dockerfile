# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

FROM python:3.12-slim

RUN pip install --no-cache-dir uv==0.8.13

WORKDIR /code

COPY ./pyproject.toml ./README.md ./uv.lock* ./
COPY ./app ./app
COPY ./static ./static

RUN uv sync --frozen --no-dev

ARG COMMIT_SHA=""
ENV COMMIT_SHA=${COMMIT_SHA}

# Run as an unprivileged user.
RUN useradd --create-home --uid 10001 studio && chown -R studio:studio /code
USER studio

EXPOSE 8080

# Binding 0.0.0.0 is required inside a container. If the port is reachable by
# others, set STUDIO_ACCESS_TOKEN so the API requires an X-Studio-Token header.
CMD ["/code/.venv/bin/uvicorn", "app.server:app", "--host", "0.0.0.0", "--port", "8080"]

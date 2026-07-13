#!/bin/sh
set -eu

cd frontend
npm run dev -- --hostname 127.0.0.1 --port 3000

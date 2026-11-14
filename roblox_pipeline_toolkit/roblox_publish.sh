#!/usr/bin/env bash

set -euo pipefail

CONFIG_FILE="publish_config.json"

load_config() {
    if [ ! -f "$CONFIG_FILE" ]; then
        echo -e "\nERROR: Missing config: $CONFIG_FILE\n"
        exit 1
    fi

    UNIVERSE_ID=$(jq -r '.universe_id' "$CONFIG_FILE" | tr -d '\r')
    PLACE_ID=$(jq -r '.place_id' "$CONFIG_FILE" | tr -d '\r')
    API_KEY=$(jq -r '.api_key' "$CONFIG_FILE" | tr -d '\r')
    RBXLX_FILE=$(jq -r '.rbxlx_file' "$CONFIG_FILE" | tr -d '\r')
    PUBLISH_ENDPOINT=$(jq -r '.publish_endpoint' "$CONFIG_FILE" | tr -d '\r')

    if [ -z "$API_KEY" ] || [ "$API_KEY" = "null" ]; then
        echo -e "\nERROR: api_key missing\n"
        exit 1
    fi

    if [ -z "$RBXLX_FILE" ] || [ "$RBXLX_FILE" = "null" ]; then
        echo -e "\nERROR: rbxlx_file missing\n"
        exit 1
    fi

    if [ -z "$PUBLISH_ENDPOINT" ] || [ "$PUBLISH_ENDPOINT" = "null" ]; then
        echo -e "\nERROR: publish_endpoint missing\n"
        exit 1
    fi

    # Ensure versionType query parameter is present
    if [[ "$PUBLISH_ENDPOINT" != *"versionType="* ]]; then
        if [[ "$PUBLISH_ENDPOINT" == *"?"* ]]; then
            PUBLISH_ENDPOINT="${PUBLISH_ENDPOINT}&versionType=Published"
        else
            PUBLISH_ENDPOINT="${PUBLISH_ENDPOINT}?versionType=Published"
        fi
    fi
}

show_config() {
    load_config
    echo
    echo "===================================="
    echo "PUBLISH CONFIG"
    echo "===================================="
    echo "Universe ID : $UNIVERSE_ID"
    echo "Place ID    : $PLACE_ID"
    echo "RBXLX File  : $RBXLX_FILE"
    echo "Endpoint    : $PUBLISH_ENDPOINT"
    echo
}

publish() {
    load_config

    if [ ! -f "$RBXLX_FILE" ]; then
        echo -e "\nERROR: Missing RBXLX: $RBXLX_FILE\n"
        exit 1
    fi

    # Set Content-Type based on file extension (.rbxlx -> application/xml, .rbxl -> application/octet-stream)
    if [[ "${RBXLX_FILE,,}" == *.rbxlx ]]; then
        CONTENT_TYPE="application/xml"
    else
        CONTENT_TYPE="application/octet-stream"
    fi

    FILE_SIZE=$(wc -c < "$RBXLX_FILE" | tr -d ' ')

    echo
    echo "===================================="
    echo "ROBLOX PUBLISH"
    echo "===================================="
    echo "Universe     : $UNIVERSE_ID"
    echo "Place        : $PLACE_ID"
    echo "File         : $RBXLX_FILE"
    echo "Content-Type : $CONTENT_TYPE"
    echo "Size         : $FILE_SIZE bytes"
    echo

    RESPONSE=$(curl -s \
        -X POST \
        "$PUBLISH_ENDPOINT" \
        -H "x-api-key: ${API_KEY}" \
        -H "Content-Type: ${CONTENT_TYPE}" \
        --data-binary @"${RBXLX_FILE}")

    mkdir -p src/templizer/generated
    echo "$RESPONSE" > publish_response.json

    VERSION=$(echo "$RESPONSE" | jq -r '.versionNumber // empty' 2>/dev/null || true)

    echo "===================================="
    echo "SERVER RESPONSE"
    echo "===================================="
    echo "$RESPONSE"
    echo

    if [ -n "$VERSION" ]; then
        cat > publish_report.json <<JSON
{
  "success": true,
  "version": ${VERSION},
  "universe_id": ${UNIVERSE_ID},
  "place_id": ${PLACE_ID},
  "file": "${RBXLX_FILE}"
}
JSON
        echo "$VERSION" > latest_version.txt
        echo "===================================="
        echo "PUBLISH SUCCESS"
        echo "===================================="
        echo "Version : $VERSION"
        echo
        exit 0
    fi

    echo "===================================="
    echo "PUBLISH FAILED"
    echo "===================================="
    echo
    exit 1
}

case "${1:-}" in
    show)
        show_config
        ;;
    publish)
        publish
        ;;
    *)
        echo
        echo "Usage:"
        echo "  ./roblox_publish.sh show"
        echo "  ./roblox_publish.sh publish"
        echo
        ;;
esac

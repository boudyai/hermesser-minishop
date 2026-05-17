#!/bin/sh
PUBLISHED="${FRONTEND_PUBLIC:-127.0.0.1:${FRONTEND_PORT:-8082}->80}"
IMAGE_TAG_VALUE="${IMAGE_TAG:-local}"
BUILD_TAG="${REMNAWAVE_MINISHOP_TAG:-${GIT_TAG:-${BUILD_TAG:-}}}"
if [ -z "$BUILD_TAG" ] && [ -r /build-tag ]; then
  BUILD_TAG="$(cat /build-tag)"
fi
BUILD_TAG="${BUILD_TAG:-unknown}"
BUILD_COMMIT="${REMNAWAVE_MINISHOP_COMMIT:-${GIT_COMMIT:-${COMMIT_SHA:-}}}"
if [ -z "$BUILD_COMMIT" ] && [ -r /build-commit ]; then
  BUILD_COMMIT="$(cat /build-commit)"
fi
BUILD_COMMIT="${BUILD_COMMIT:-unknown}"
DISPLAY_IMAGE_TAG="$IMAGE_TAG_VALUE"
if [ "$IMAGE_TAG_VALUE" = "latest" ] && [ "$BUILD_TAG" != "unknown" ]; then
  DISPLAY_IMAGE_TAG="latest-${BUILD_TAG}"
elif [ "$IMAGE_TAG_VALUE" = "dev" ]; then
  if [ "$BUILD_TAG" != "unknown" ] && [ "$BUILD_COMMIT" != "unknown" ]; then
    DISPLAY_IMAGE_TAG="dev-${BUILD_TAG}+${BUILD_COMMIT}"
  elif [ "$BUILD_TAG" != "unknown" ]; then
    DISPLAY_IMAGE_TAG="dev-${BUILD_TAG}"
  elif [ "$BUILD_COMMIT" != "unknown" ]; then
    DISPLAY_IMAGE_TAG="dev+${BUILD_COMMIT}"
  fi
fi

cat <<EOF

              ~ ~ ~  r e m n a w a v e  ~ ~ ~

  ███╗   ███╗██╗███╗   ██╗██╗███████╗██╗  ██╗ ██████╗ ██████╗
  ████╗ ████║██║████╗  ██║██║██╔════╝██║  ██║██╔═══██╗██╔══██╗
  ██╔████╔██║██║██╔██╗ ██║██║███████╗███████║██║   ██║██████╔╝
  ██║╚██╔╝██║██║██║╚██╗██║██║╚════██║██╔══██║██║   ██║██╔═══╝
  ██║ ╚═╝ ██║██║██║ ╚████║██║███████║██║  ██║╚██████╔╝██║
  ╚═╝     ╚═╝╚═╝╚═╝  ╚═══╝╚═╝╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚═╝

              container :: FRONTEND
              image tag :: ${DISPLAY_IMAGE_TAG}
              commit :: ${BUILD_COMMIT}
              listen :: :80
              published :: ${PUBLISHED}
              upstream :: backend:8081
              healthcheck :: /health
         https://github.com/3252a8/remnawave-minishop

EOF

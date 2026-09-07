# Pre-built (optimized) Keycloak image for the local/test stack.
#
# Plain `kc.sh start` re-runs the Quarkus augmentation on every container start when
# build-time options (db, cache) differ from the stock image: ~2 min per start. Baking
# them in here and starting with `--optimized` skips that.
ARG KC_VERSION
FROM quay.io/keycloak/keycloak:${KC_VERSION}

ARG KC_DB=postgres
ENV KC_DB=${KC_DB}

# Single node: local cache, no JGroups discovery. With the default `ispn` stack a fresh
# container first tries to JOIN stale members left in jgroups_ping by a previous
# container and burns ~1 min on JOIN timeouts before giving up.
ENV KC_CACHE=local

RUN /opt/keycloak/bin/kc.sh build

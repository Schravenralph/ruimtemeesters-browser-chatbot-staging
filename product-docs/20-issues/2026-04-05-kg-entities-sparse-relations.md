# Knowledge Graph Entities Have Sparse Relations

**Date:** 2026-04-05
**Severity:** low
**Service:** Ruimtemeesters-Databank (GraphDB)
**Phase found:** benchmark

## Description

Many KG entities have 0 neighbors. For example, the "Overgangsregels tijdelijk deel omgevingsplan (bruidsschat)" Regulation entity has no incoming or outgoing relations, despite being a central concept that should link to Bkl instructieregels, specific articles (22.26-22.39), and related PolicyDocuments.

The KG has 10,276 entities but only 6,019 relations — under 0.6 relations per entity on average.

## Impact

Graph traversal from isolated entities returns only the starting node. The chatbot can't follow concept chains (e.g., bruidsschat → Bkl instructieregels → geluid/geur/trillingen → specific articles).

## Fix

Enrich the KG extraction pipeline to:

1. Link Regulation entities to the PolicyDocuments they were extracted from
2. Link related Regulations to each other (e.g., bruidsschat articles cross-reference each other)
3. Link SpatialUnit entities to applicable Regulations via APPLIES_TO

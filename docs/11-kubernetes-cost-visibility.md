# Kubernetes cost visibility (advanced, not implemented here)

This one's marked as not implemented deliberately, because it's a
meaningfully different problem from everything else in this repo and
deserves to be called out rather than half-modeled.

## Why Kubernetes cost is a different problem

Everywhere else in this project, "a resource" and "a cost line item" are
basically the same thing - one EC2 instance, one cost. On a Kubernetes
cluster, the cloud provider bills you for nodes (VMs), and the cluster
then runs many workloads, from many teams, packed onto those shared
nodes. The bill you get from AWS/Azure/GCP has no idea that node
`ip-10-0-1-42` was running 40% `checkout-service` pods and 60%
`recommendation-engine` pods this week - from the cloud's perspective
there's just one VM. Getting cost per namespace, per deployment, or per
team out of that requires a second layer that:

1. Reads actual resource requests/limits and usage from the Kubernetes API
   and metrics pipeline (metrics-server, Prometheus) for every pod.
2. Allocates each node's cost across the pods scheduled on it,
   proportional to what they've requested or consumed (there are multiple
   defensible allocation methods here - by request, by actual usage, or a
   blend - and which one you pick materially changes the numbers each team
   sees).
3. Handles shared/overhead costs (system pods, unschedulable capacity from
   bin-packing inefficiency, cluster-autoscaler headroom) somehow, usually
   by allocating them proportionally too rather than leaving them
   unattributed.

This is genuinely most of the engineering effort in tools like
[OpenCost](https://www.opencost.io/) and
[Kubecost](https://www.kubecost.com/), which exist specifically because
this allocation problem is hard enough that most teams reach for a
dedicated tool rather than building it themselves.

## How it would extend this project's model

If you wanted to add this, the natural approach is to keep `CostRecord`'s
top-level `provider`/`account_id`/`service`/`region` as the node's cloud
billing identity, and add Kubernetes-specific dimensions into `tags`
(`namespace`, `workload`, `pod_owner_kind`, whatever your allocation model
needs) rather than into new top-level columns - since Kubernetes dimensions
only apply to the subset of cost records that are container-orchestrated
compute, not to a managed database or a storage bucket. A dedicated
allocation step would sit between "read node cost + pod metrics" and
"insert into `cost_records`," splitting one node's hourly cost into
multiple `CostRecord` rows (one per namespace/workload sharing that node
during that hour) before they ever reach the ingestion pipeline this
project already has.

None of the analytics code in `finops/analytics/` would need to change to
support this - `cost_by_dimension(conn, "team", ...)` already works
against whatever's in the `team` column regardless of whether that row
represents a whole EC2 instance or one workload's allocated slice of a
shared node's cost.

Next: [12-going-to-production.md](12-going-to-production.md).

from typing import List, Dict, Any, Set
from app.models import domain
from app.assurance.config import (
    INDEPENDENCE_HIGH,
    INDEPENDENCE_MODERATE,
    INDEPENDENCE_LOW,
    INDEPENDENCE_UNKNOWN,
    SHARED_EVIDENCE_DEPENDENCY_THRESHOLD,
)


def evaluate_evidence_dependencies(findings: List[domain.Finding]) -> Dict[str, Any]:
    """
    Evaluate evidence overlap and dependencies across generated supervisory findings.
    Determines whether multiple findings rely upon identical underlying source records.
    """
    if not findings:
        return {
            "status": INDEPENDENCE_UNKNOWN,
            "shared_cluster_count": 0,
            "max_overlap_ratio": 0.0,
            "explanation": "No findings available to evaluate evidence independence.",
        }

    findings_with_evidence = [f for f in findings if f.evidence_ids and len(f.evidence_ids) > 0]

    if len(findings_with_evidence) <= 1:
        return {
            "status": INDEPENDENCE_HIGH,
            "shared_cluster_count": 0,
            "max_overlap_ratio": 0.0,
            "explanation": "Single finding or independent evidence sets observed.",
        }

    shared_clusters: List[Dict[str, Any]] = []
    max_overlap = 0.0

    n = len(findings_with_evidence)
    for i in range(n):
        set_a = set(findings_with_evidence[i].evidence_ids)
        for j in range(i + 1, n):
            set_b = set(findings_with_evidence[j].evidence_ids)
            intersection = set_a.intersection(set_b)
            union = set_a.union(set_b)

            if union:
                jaccard = len(intersection) / len(union)
                overlap_a = len(intersection) / len(set_a) if set_a else 0
                overlap_b = len(intersection) / len(set_b) if set_b else 0
                max_pair_overlap = max(overlap_a, overlap_b)
                if max_pair_overlap > max_overlap:
                    max_overlap = max_pair_overlap

                if len(intersection) > 0 and max_pair_overlap >= SHARED_EVIDENCE_DEPENDENCY_THRESHOLD:
                    shared_clusters.append({
                        "finding_1": findings_with_evidence[i].id,
                        "finding_2": findings_with_evidence[j].id,
                        "shared_evidence_count": len(intersection),
                        "shared_evidence_sample": list(intersection)[:5],
                        "overlap_ratio": round(max_pair_overlap, 2),
                    })

    if len(shared_clusters) > 0 or max_overlap >= SHARED_EVIDENCE_DEPENDENCY_THRESHOLD:
        status = INDEPENDENCE_LOW
        explanation = f"Low evidence independence: {len(shared_clusters)} pair(s) of findings share >{SHARED_EVIDENCE_DEPENDENCY_THRESHOLD * 100:.0f}% of identical underlying source records."
    elif max_overlap > 0.2:
        status = INDEPENDENCE_MODERATE
        explanation = f"Moderate evidence independence: Some source records are referenced across multiple findings (max overlap: {max_overlap * 100:.1f}%)."
    else:
        status = INDEPENDENCE_HIGH
        explanation = "High evidence independence: Findings rely on distinct operational evidence subsets."

    return {
        "status": status,
        "shared_cluster_count": len(shared_clusters),
        "max_overlap_ratio": round(max_overlap, 2),
        "clusters": shared_clusters,
        "explanation": explanation,
    }

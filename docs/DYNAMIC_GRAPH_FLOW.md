# Dynamic Graph Flow for LinkedIn Influencer Selection

## Complete Flow Diagram

```mermaid
graph TB
    Start([Start Scraping Run]) --> LoadState[Load Existing Graph<br/>- nodes table<br/>- edges table]
    
    LoadState --> BuildCandidates[Build Candidate Set<br/>- All 51 seeds<br/>- Non-seeds with edges from seeds]
    
    BuildCandidates --> ComputeProximity[Compute Proximity Scores<br/>For each candidate node u:<br/>proximity = Σ seeds Σ edges weight × α_type]
    
    ComputeProximity --> SelectBatch[Select Next Batch<br/>- Top K_core seeds<br/>- Top K_discovery non-seeds]
    
    SelectBatch --> ScrapeProfiles[Scrape Selected Profiles]
    
    ScrapeProfiles --> ExtractFollowers[Extract Followers<br/>Create FOLLOWER edges<br/>follower → influencer]
    
    ExtractFollowers --> ExtractConnections[Extract Connections<br/>Create CONNECTION edges<br/>A ↔ C bidirectional]
    
    ExtractConnections --> ExtractPosts[Extract Posts<br/>- Extract tagged_profiles → TAG edges<br/>- Extract reposts → REPOST edges]
    
    ExtractPosts --> UpdateGraph[Update Graph<br/>- Add new nodes<br/>- Add/update edges<br/>- Set last_seen_at]
    
    UpdateGraph --> ApplyDecay[Apply Time Decay<br/>weight = weight × exp-λ×Δt<br/>Drop edges with weight < ε]
    
    ApplyDecay --> RecomputeScores[Recompute Node Summaries<br/>incoming_tag_weight_from_seeds<br/>incoming_repost_weight_from_seeds]
    
    RecomputeScores --> SaveState[Save Updated Graph<br/>- nodes table<br/>- edges table]
    
    SaveState --> End([End - Next Run Starts])
    
    style Start fill:#e1f5ff
    style End fill:#e1f5ff
    style ScrapeProfiles fill:#fff4e1
    style ComputeProximity fill:#e8f5e9
    style ApplyDecay fill:#fce4ec
```

## Graph Structure Diagram

```mermaid
graph LR
    subgraph "Seed Influencers"
        S1[Seed 1<br/>chiphuyen]
        S2[Seed 2<br/>andrewyng]
        S3[Seed 3<br/>yann-lecun]
    end
    
    subgraph "Discovered Profiles"
        D1[Profile A<br/>prrao87]
        D2[Profile B<br/>ankur-gupta]
        D3[Profile C<br/>student-xyz]
    end
    
    S1 -->|REPOST<br/>weight: 3.0| D1
    S1 -->|TAG<br/>weight: 2.0| D2
    S2 -->|REPOST<br/>weight: 3.0| D1
    S2 -->|CONNECTION<br/>weight: 1.0| D2
    S3 -->|FOLLOWER<br/>weight: 0.5| D1
    
    S1 -.->|TAG<br/>filtered out| D3
    
    style S1 fill:#4caf50
    style S2 fill:#4caf50
    style S3 fill:#4caf50
    style D1 fill:#2196f3
    style D2 fill:#2196f3
    style D3 fill:#ff9800,stroke-dasharray: 5 5
```

## Proximity Score Calculation

```mermaid
graph TB
    subgraph "Input"
        Node[Node u<br/>prrao87]
        Seeds[Seed Influencers<br/>chiphuyen, andrewyng, ...]
        Edges[Edges Table<br/>src, dst, type, weight]
    end
    
    subgraph "Alpha Weights"
        Alpha[α_REPOST = 3.0<br/>α_TAG = 2.0<br/>α_CONNECTION = 1.0<br/>α_FOLLOWER = 0.5]
    end
    
    subgraph "Calculation"
        Loop1[For each seed s]
        Loop2[For each edge e: s → u]
        Multiply[score += weight × α_type]
        Sum[Sum all contributions]
    end
    
    subgraph "Output"
        Proximity[proximity_to_seeds<br/>Example: 9.5]
    end
    
    Node --> Loop1
    Seeds --> Loop1
    Edges --> Loop2
    Alpha --> Multiply
    Loop1 --> Loop2
    Loop2 --> Multiply
    Multiply --> Sum
    Sum --> Proximity
    
    style Proximity fill:#4caf50
    style Alpha fill:#ff9800
```

## Edge Types and Weights

```mermaid
graph TB
    subgraph "Edge Types"
        REPOST[REPOST<br/>influencer → original_author<br/>α = 3.0]
        TAG[TAG<br/>influencer → tagged_profile<br/>α = 2.0]
        CONNECTION[CONNECTION<br/>influencer ↔ connection<br/>α = 1.0]
        FOLLOWER[FOLLOWER<br/>follower → influencer<br/>α = 0.5]
    end
    
    subgraph "Weight Decay"
        Decay[weight = weight × exp-λ×Δt<br/>λ = decay rate<br/>Δt = hours since last_seen]
        Threshold[Drop if weight < ε<br/>ε = 0.01]
    end
    
    REPOST --> Decay
    TAG --> Decay
    CONNECTION --> Decay
    FOLLOWER --> Decay
    
    Decay --> Threshold
    
    style REPOST fill:#f44336
    style TAG fill:#ff9800
    style CONNECTION fill:#2196f3
    style FOLLOWER fill:#9e9e9e
```

## Selection Strategy

```mermaid
graph TB
    Candidates[All Candidates<br/>- 51 seeds<br/>- Discovered non-seeds]
    
    ComputeProximity[Compute proximity_to_seeds<br/>for each candidate]
    
    Sort[Sort by proximity score<br/>descending]
    
    Split[Split into two groups]
    
    SeedsGroup[Seeds Group<br/>Select top K_core<br/>e.g., top 30]
    
    NonSeedsGroup[Non-Seeds Group<br/>Select top K_discovery<br/>e.g., top 20]
    
    Randomize[Optional: Randomize<br/>within top bands<br/>for exploration]
    
    FinalBatch[Final Batch<br/>K_core + K_discovery<br/>profiles to scrape]
    
    Candidates --> ComputeProximity
    ComputeProximity --> Sort
    Sort --> Split
    Split --> SeedsGroup
    Split --> NonSeedsGroup
    SeedsGroup --> Randomize
    NonSeedsGroup --> Randomize
    Randomize --> FinalBatch
    
    style FinalBatch fill:#4caf50
    style SeedsGroup fill:#e3f2fd
    style NonSeedsGroup fill:#fff3e0
```

## Data Collection During Scraping

```mermaid
graph TB
    Scrape[Scrape Profile A]
    
    Scrape --> GetFollowers[Get Followers List<br/>Sample followers]
    Scrape --> GetConnections[Get Connections List<br/>1st, 2nd, 3rd degree]
    Scrape --> GetPosts[Get Recent Posts<br/>Extract metadata]
    
    GetFollowers --> CreateFollowerEdges[Create FOLLOWER edges<br/>F → A<br/>weight = 1.0<br/>last_seen_at = now]
    
    GetConnections --> CreateConnectionEdges[Create CONNECTION edges<br/>A ↔ C<br/>bidirectional<br/>weight = 1.0<br/>last_seen_at = now]
    
    GetPosts --> ExtractTags[Extract tagged_profiles<br/>from each post]
    GetPosts --> ExtractReposts[Extract reposts<br/>is_repost + original_author]
    
    ExtractTags --> CreateTagEdges[Create TAG edges<br/>A → T<br/>weight = 1.0<br/>last_seen_at = now]
    
    ExtractReposts --> CreateRepostEdges[Create REPOST edges<br/>A → O<br/>weight = 1.0<br/>last_seen_at = now]
    
    CreateFollowerEdges --> UpdateGraph
    CreateConnectionEdges --> UpdateGraph
    CreateTagEdges --> UpdateGraph
    CreateRepostEdges --> UpdateGraph
    
    UpdateGraph[Update Graph<br/>Add nodes if new<br/>Update edges<br/>Merge weights]
    
    style Scrape fill:#e1f5ff
    style UpdateGraph fill:#4caf50
```

## Filtering Noisy Taggers

```mermaid
graph TB
    TaggedProfile[Tagged Profile T<br/>from influencer A]
    
    CheckFilters{Passes Filters?<br/>- followers >= threshold<br/>- Not student/intern<br/>- Decent tech ratio}
    
    CheckFilters -->|No| FilterOut[Filter Out<br/>Don't create edge]
    
    CheckFilters -->|Yes| CheckInfluence{Is A a<br/>strong seed?}
    
    CheckInfluence -->|Yes| HighWeight[Create TAG edge<br/>A → T<br/>weight = 1.0 × influence]
    
    CheckInfluence -->|No| LowWeight[Create TAG edge<br/>A → T<br/>weight = 0.1 × influence]
    
    HighWeight --> CheckMultiple{Multiple seeds<br/>tagged T?}
    LowWeight --> CheckMultiple
    
    CheckMultiple -->|Yes| HighPriority[High Priority<br/>Add to candidate set]
    
    CheckMultiple -->|No| LowPriority[Low Priority<br/>May not be selected]
    
    style FilterOut fill:#f44336
    style HighPriority fill:#4caf50
    style LowPriority fill:#ff9800
```

## Complete System Architecture

```mermaid
graph TB
    subgraph "Storage Layer"
        NodesDB[(Nodes Table<br/>profile_url, followers_count<br/>is_seed, last_scraped_at)]
        EdgesDB[(Edges Table<br/>src, dst, type<br/>weight, last_seen_at)]
    end
    
    subgraph "Graph Engine"
        LoadGraph[Load Graph]
        UpdateGraph[Update Graph]
        DecayGraph[Apply Decay]
        ScoreNodes[Score Nodes]
    end
    
    subgraph "Selection Engine"
        BuildCandidates[Build Candidates]
        ComputeProximity[Compute Proximity]
        SelectBatch[Select Batch]
    end
    
    subgraph "Scraping Layer"
        ScrapeProfiles[Scrape Profiles]
        ExtractRelations[Extract Relations<br/>FOLLOWER, CONNECTION<br/>TAG, REPOST]
    end
    
    NodesDB --> LoadGraph
    EdgesDB --> LoadGraph
    
    LoadGraph --> BuildCandidates
    BuildCandidates --> ComputeProximity
    ComputeProximity --> SelectBatch
    
    SelectBatch --> ScrapeProfiles
    ScrapeProfiles --> ExtractRelations
    
    ExtractRelations --> UpdateGraph
    UpdateGraph --> DecayGraph
    DecayGraph --> ScoreNodes
    
    ScoreNodes --> NodesDB
    UpdateGraph --> EdgesDB
    
    ScoreNodes --> BuildCandidates
    
    style NodesDB fill:#e3f2fd
    style EdgesDB fill:#e3f2fd
    style ScrapeProfiles fill:#fff3e0
    style SelectBatch fill:#4caf50
```

# Spatial Equity: What Patterns Characterized How Lower Manhattan Blocks Were Prioritized for Testing?

## 1. Project Overview

This project examines the spatial distribution of environmental testing-related archival records across Lower Manhattan following the September 11 attacks.

The analysis focuses on three main questions:

- How were testing-related records distributed across buildings and Tax Blocks?
- Did testing patterns differ across building types?
- Were building characteristics associated with testing presence?

## 2. Data and Analysis

The dataset was filtered to include 970 unique buildings across 126 Lower Manhattan Tax Blocks.

The analysis was organized into three parts:

### 2.1 Spatial Distribution of Testing-Related Records

- Matched building identifiers (BINs) with Tax Block information using BBLs and NYC Building Footprints data.
- Defined building-level testing presence as having at least one associated testing-related page.
- Calculated testing coverage across buildings and Tax Blocks.
- Used heatmaps to visualize the spatial distribution of testing-related page associations and building-level testing coverage.

### 2.2 Building Type Analysis

- Classified buildings into residential, office, retail/commercial, hospitality, mixed-use, and other categories.
- Used Chi-square tests to examine differences in testing presence across building types.
- Applied Kruskal–Wallis tests and post-hoc pairwise comparisons to examine differences in testing-page counts among buildings with testing records.

### 2.3 Building Characteristics Analysis

- Compared tested and untested buildings based on building area, number of floors, year built, and unit counts.
- Conducted Mann–Whitney U tests and Welch's t-tests.
- Examined correlations between building characteristics and testing-page counts using Spearman correlation.
- Used multiple logistic regression to examine the relationship between building characteristics and testing presence.

## 3. Key Findings

### 3.1 Spatial Distribution

- Overall building-level testing coverage was 35.6% among the 970 sampled buildings.
- Testing-related archival records were unevenly distributed across buildings and Tax Blocks.
- A higher volume of associated testing pages did not necessarily indicate higher building-level testing coverage.

### 3.2 Building Type

- Testing presence did not differ significantly across building types (Chi-square test, p = 0.821).
- Testing-page counts among buildings with testing records showed significant overall differences across building types (Kruskal–Wallis test, p = 0.008).
- Hospitality buildings had the highest mean number of associated testing pages, while mixed-use buildings had the lowest.
- However, no individual pairwise differences remained statistically significant after Holm correction.

### 3.3 Building Characteristics

- Mann–Whitney U tests identified significant differences between tested and untested buildings in building area, number of floors, year built, and total units.
- Welch's t-tests confirmed significant differences in mean building area and year built.
- Spearman correlation analysis showed weak but statistically significant positive associations between the five examined building characteristics and testing-page counts.
- In the multiple logistic regression model, building area remained significantly associated with testing presence after controlling for floors and year built (OR = 1.290, p = 0.005). Floors and year built were not statistically significant in the adjusted model.

## 4. Overall Conclusion

The analysis found that testing-related archival records were unevenly distributed across Lower Manhattan buildings and Tax Blocks.

Building type was not significantly associated with testing presence, while building area showed the most consistent association across the building-level analyses.

The findings also highlight the importance of distinguishing between testing-page volume and building-level testing presence, as these measures capture different aspects of the archival record distribution.

The logistic regression model had limited explanatory power, suggesting that other factors may also be relevant to understanding the observed patterns.

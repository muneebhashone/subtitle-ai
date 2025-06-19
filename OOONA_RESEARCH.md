# OOONA Format Research Report

## Overview
Research conducted to evaluate feasibility of adding `.ooona` subtitle format support to SubsAI.

## What is .ooona Format?
- **Type**: Proprietary subtitle format
- **Owner**: OOONA Tools (media localization company)
- **Extension**: `.ooona`
- **Usage**: Internal format for OOONA's platform ecosystem

## Research Findings

### 1. Library Support
- ❌ No Python libraries support .ooona format
- ❌ Not supported by pysubs2 (our current subtitle library)
- ❌ No open-source parsers found
- ❌ No community implementations discovered

### 2. Format Accessibility
- ❌ **Proprietary & Closed**: Format is owned by OOONA Tools
- ❌ **No Public Specification**: Technical documentation not available
- ❌ **No Official Developer Docs**: Format details not openly shared
- ❌ **Limited Access**: Can only create .ooona files through OOONA's paid platform

### 3. OOONA API Investigation
**Available APIs:**
- Convert API (subtitle format conversion)
- QC API (subtitle file validation)

**API Limitations:**
- ❌ Documentation requires authentication/paid access
- ❌ No public endpoint URLs available
- ❌ No confirmation that .ooona format is supported in API conversions
- ❌ APIs appear designed for standard formats (SRT, VTT), not proprietary .ooona
- 💰 Requires paid subscription (1,000-10,000 conversions/month)

### 4. Supported Formats by OOONA
OOONA Tools supports 50+ subtitle formats including:
- ✅ .ooona (confirmed as supported format)
- ✅ Standard formats: SRT, VTT, ASS, TTML, etc.
- ✅ Ooona Project (.json)

## Implementation Challenges

### Technical Barriers
1. **No Format Specification**: Would require reverse engineering
2. **Legal Risks**: Reverse engineering may violate terms of service
3. **No Library Foundation**: Would need to build parser from scratch
4. **Maintenance Burden**: Format could change without notice

### Business Considerations
1. **Limited Demand**: Very few users likely need this specific format
2. **High Development Cost**: Significant time investment for uncertain outcome
3. **Legal Complications**: Potential intellectual property issues
4. **No Ongoing Support**: No official support from OOONA for external implementations

## Alternatives Considered

### Option 1: Direct Contact with OOONA
- **Pros**: Official support, proper documentation
- **Cons**: Likely to be refused (proprietary format), potential licensing costs
- **Assessment**: Low probability of success

### Option 2: Reverse Engineering
- **Pros**: Technically possible with sample files
- **Cons**: Legal risks, time-consuming, no guarantee of success
- **Assessment**: High risk, uncertain outcome

### Option 3: API Integration
- **Pros**: Official integration path
- **Cons**: Requires paid access, limited functionality, unclear .ooona support
- **Assessment**: Not viable (APIs don't appear to support .ooona export)

## Recommendation

### ❌ DO NOT IMPLEMENT .ooona FORMAT SUPPORT

**Reasons:**
1. **Legal Risk**: Reverse engineering proprietary formats
2. **No Foundation**: No existing libraries to build upon
3. **Limited Benefit**: Very small user base
4. **High Cost**: Significant development effort
5. **Uncertain Outcome**: No guarantee of successful implementation

### ✅ RECOMMENDED ALTERNATIVES

Focus on these **open formats** instead:

| Format | Standard | Benefits |
|--------|----------|----------|
| **TTML** | W3C Standard | Broadcast industry standard, XML-based |
| **DFXP** | Industry Standard | Distribution format, wide adoption |
| **SBV** | YouTube Format | High user demand, simple format |
| **Enhanced WebVTT** | Web Standard | Modern web standard with styling |

**Why these alternatives are better:**
- ✅ Public specifications available
- ✅ Existing pysubs2 library support
- ✅ Wide industry adoption
- ✅ No legal complications
- ✅ Better return on development investment

## Conclusion

The `.ooona` format is a proprietary, closed format with no viable implementation path for open-source projects. Development efforts should focus on open, standardized subtitle formats that provide broader user value and legal safety.

**Next Steps**: Implement support for open formats (TTML, DFXP, SBV) which will benefit more users and align with industry standards.

---
*Research conducted: June 2025*  
*Status: Investigation Complete - Implementation Not Recommended*
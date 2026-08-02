# Novel Export to ZIP Feature

**Date**: 2026-08-02  
**Type**: Feature Implementation  
**Component**: Novel Library

## Overview

Build a novel export feature that allows users to download a ZIP file containing the novel's metadata (as JSON) and all chapter content as individual text files.

## User Story

As a user reading a novel in the library, I want to click an Export button in the NovelReader header to download the entire novel as a ZIP file, so I can read it offline or archive it locally.

## Technical Design

### Backend Implementation

#### Endpoint Specification

- **Route**: `PATCH /api/novels/{id}/export`
- **Method**: PATCH
- **Authorization**: Required (SessionUser)
- **Response Type**: `application/zip` (binary stream)
- **Response Headers**: `Content-Disposition: attachment; filename="{novel_title}.zip"`

#### Implementation Steps

1. **Route Handler** (`srcs/backend/app/routers/novels.py`)
   - Add new route after `delete_novel_route`
   - Use `SessionUser`, `RepositoryNovelDep`, `ServiceNovelBindingDep` dependencies
   - Fetch novel with ownership validation (404 if not owned by user)
   - Fetch chapters via `binding_service.get_detail(novel_id)`

2. **ZIP Generation**
   - Use `io.BytesIO` for in-memory buffer
   - Use `zipfile.ZipFile` (Python stdlib) in write mode
   - Generate `novel.json` with complete metadata:
     - id, title, author, description, language, tags, notes
     - chapterCount, binding info (scrapingId, boundAt, lastSyncedAt)
     - createdAt, updatedAt, etag
   - Generate `{chapter_title}.txt` files:
     - Sanitize filenames: remove special chars (`/\:*?"<>|`)
     - Limit length to 100 characters
     - Handle duplicates with numeric suffix (_1, _2, etc.)
     - Join content paragraphs with double newlines (`\n\n`)
     - Create empty files for chapters without content

3. **Streaming Response**
   - Return `StreamingResponse` with ZIP bytes
   - Set proper media type and content disposition
   - Error handling: `NotFoundException` for missing/unauthorized novels

#### Filename Sanitization Algorithm

```python
def sanitize_filename(title: str, max_length: int = 100) -> str:
    # Remove forbidden characters
    forbidden = r'/\:*?"<>|'
    for char in forbidden:
        title = title.replace(char, '_')
    # Trim and clean
    title = title.strip()
    # Limit length
    if len(title) > max_length:
        title = title[:max_length].rstrip()
    return title or 'chapter'
```

### Frontend Implementation

#### UI Changes

**Location**: `srcs/frontend/app/components/library/NovelReader.vue`

- Add Export button in `<template #right>` section after Edit button
- Button properties:
  - label: "Export"
  - icon: "lucide:download"
  - color: "primary"
  - size: "sm"
  - Visibility condition: `chapter && content && !editing` (same as Edit)
  - Loading state during export operation

#### API Integration

**Location**: `srcs/frontend/app/composables/useNovelWorkspaceApi.ts`

Add `exportNovel(novelId: string)` method:
- Call generated API client
- Return raw response for blob handling
- Handle errors with try/catch

#### Download Handler

In NovelReader component:
1. Add `exporting` ref for loading state
2. Create `exportNovel()` async method:
   - Call API via composable
   - Create Blob from response bytes
   - Generate object URL with `URL.createObjectURL()`
   - Create temporary anchor element
   - Set `download` attribute with sanitized filename
   - Programmatically click to trigger download
   - Revoke object URL to free memory
3. Add error handling with toast notifications

#### Pattern Reference

Similar to audio download in `AudioChapterReader.vue`:
```typescript
const blob = new Blob([response], { type: 'application/zip' })
const url = URL.createObjectURL(blob)
const link = document.createElement('a')
link.href = url
link.download = `${novel.title}.zip`
link.click()
URL.revokeObjectURL(url)
```

### API Client Generation

After backend implementation, regenerate TypeScript client:
```bash
cd srcs/frontend
pnpm generate:api
```

## Implementation Phases

### Phase 1: Backend Foundation
1. Create ZIP export endpoint
2. Implement ZIP generation logic
3. Add filename sanitization
4. Return streaming response

### Phase 2: Frontend Integration (parallel with Phase 1 completion)
1. Add Export button to NovelReader
2. Implement export API method in composable
3. Create download handler with blob URL

### Phase 3: Integration
1. Regenerate API client
2. Wire up button to handler
3. Add loading states and error handling

## Testing Strategy

### Manual Testing

1. **Happy Path**
   - Log in and open a novel with chapters
   - Open any chapter in NovelReader
   - Click Export button
   - Verify ZIP downloads with correct filename
   - Extract and verify contents

2. **Content Verification**
   - Verify `novel.json` has all metadata fields
   - Verify one `.txt` file per chapter
   - Verify chapter content is properly formatted
   - Verify empty files for unavailable content

3. **Edge Cases**
   - Novel with special characters in title
   - Chapters with special characters in titles
   - Novel with no chapters
   - Novel with chapters but no content
   - Very long chapter titles (>100 chars)
   - Duplicate chapter titles

4. **Security**
   - Attempt to export another user's novel (should fail with 404)
   - Verify ownership check is enforced

### Automated Testing

Future considerations (not in initial scope):
- Backend unit tests for ZIP generation
- Backend integration tests for endpoint
- Frontend component tests for button visibility
- E2E tests for download flow

## Dependencies

### Backend
- Python stdlib: `zipfile`, `io`, `json`
- FastAPI: `StreamingResponse`
- Existing services: `NovelBindingService`, `NovelRepository`

### Frontend
- Existing: Nuxt UI components, composables
- Browser APIs: Blob, URL.createObjectURL

## Acceptance Criteria

- [ ] Export button appears in NovelReader header next to Edit button
- [ ] Button is only visible when chapter content is loaded
- [ ] Clicking Export downloads a ZIP file named `{novel_title}.zip`
- [ ] ZIP contains `novel.json` with complete novel metadata
- [ ] ZIP contains one `.txt` file per chapter with sanitized names
- [ ] Chapter files contain content paragraphs separated by double newlines
- [ ] Chapters without content have empty `.txt` files
- [ ] Filenames are sanitized (no forbidden characters)
- [ ] Duplicate chapter titles get numeric suffixes
- [ ] Loading state shows during export operation
- [ ] Error toast appears on export failure
- [ ] Users cannot export novels they don't own (404 error)

## Future Enhancements

- Translation support (language parameter)
- Selective chapter export (choose which chapters)
- Export format options (PDF, EPUB, markdown)
- Progress indicator for large novels
- Export from novel list page (without opening reader)
- Batch export multiple novels

## Related Files

### Backend
- `srcs/backend/app/routers/novels.py` - Export route
- `srcs/backend/app/services/novel_binding_service.py` - Data fetching
- `srcs/backend/app/domain/novels.py` - Domain models
- `srcs/backend/app/domain/responses.py` - Response models

### Frontend
- `srcs/frontend/app/components/library/NovelReader.vue` - Export button
- `srcs/frontend/app/composables/useNovelWorkspaceApi.ts` - API method
- `srcs/frontend/shared/api-services/srv-core.client.ts` - Generated client

## References

- Existing workspace export pattern: `srcs/backend/app/routers/workspaces.py` (lines 190-270)
- Audio download pattern: `srcs/frontend/app/components/workspaces/AudioChapterReader.vue` (line 252)
- Novel authorization pattern: `srcs/backend/app/routers/novels.py` `get_novel_route`

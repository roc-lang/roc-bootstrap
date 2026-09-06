#include "llvm/CodeGen/LiveInterval.h"
#include "gtest/gtest.h"
#include <array>
using namespace llvm;

TEST(LiveRangeTest, LiveAtSortedIndexesMatchesSegmentMembership) {
  // Exhaust all disjoint half-open ranges and all sorted query sets in a
  // small universe. This includes empty inputs, endpoints, and multiple holes.
  std::array<IndexListEntry, 8> Entries = {
      IndexListEntry(nullptr, 0), IndexListEntry(nullptr, 16),
      IndexListEntry(nullptr, 32), IndexListEntry(nullptr, 48),
      IndexListEntry(nullptr, 64), IndexListEntry(nullptr, 80),
      IndexListEntry(nullptr, 96), IndexListEntry(nullptr, 112)};
  std::array<SlotIndex, 8> Indexes;
  for (unsigned I = 0; I != 8; ++I)
    Indexes[I] = SlotIndex(&Entries[I], 0);
  VNInfo Value(0, Indexes[0]);
  for (unsigned Mask = 0; Mask != 128; ++Mask) {
    LiveRange Range;
    for (unsigned I = 0; I != 7;) {
      if (!(Mask & (1U << I))) { ++I; continue; }
      unsigned Start = I++;
      while (I != 7 && (Mask & (1U << I))) ++I;
      Range.segments.emplace_back(Indexes[Start], Indexes[I], &Value);
    }
    for (unsigned Query = 0; Query != 256; ++Query) {
      SmallVector<SlotIndex> Slots;
      bool Expected = false;
      for (unsigned I = 0; I != 8; ++I) {
        if (!(Query & (1U << I))) continue;
        Slots.push_back(Indexes[I]);
        Expected |= I < 7 && (Mask & (1U << I));
      }
      EXPECT_EQ(Expected, Range.isLiveAtIndexes(Slots))
          << "range " << Mask << " query " << Query;
    }
  }
}

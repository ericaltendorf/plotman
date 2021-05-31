# version = 1.0.2
# https://github.com/Chia-Network/chiapos/blob/1.0.2/LICENSE
# https://github.com/Chia-Network/chiapos/blob/1.0.2/src/pos_constants.hpp
# start ported code
# Unique plot id which will be used as a ChaCha8 key, and determines the PoSpace.
kIdLen = 32;

# Distance between matching entries is stored in the offset
kOffsetSize = 10;

# Max matches a single entry can have, used for hardcoded memory allocation
kMaxMatchesSingleEntry = 30;
kMinBuckets = 16;
kMaxBuckets = 128;

# During backprop and compress, the write pointer is ahead of the read pointer
# Note that the large the offset, the higher these values must be
kReadMinusWrite = 1 << kOffsetSize;
kCachedPositionsSize = kReadMinusWrite * 4;

# Must be set high enough to prevent attacks of fast plotting
kMinPlotSize = 18;

# Set to 50 since k + kExtraBits + k*4 must not exceed 256 (BLAKE3 output size)
kMaxPlotSize = 50;

# The amount of spare space used for sort on disk (multiplied time memory buffer size)
kSpareMultiplier = 5;

# The proportion of memory to allocate to the Sort Manager for reading in buckets and sorting them
# The lower this number, the more memory must be provided by the caller. However, lowering the
# number also allows a higher proportion for writing, which reduces seeks for HDD.
kMemSortProportion = 0.75;
kMemSortProportionLinePoint = 0.85;

# How many f7s per C1 entry, and how many C1 entries per C2 entry
kCheckpoint1Interval = 10000;
kCheckpoint2Interval = 10000;

# F1 evaluations are done in batches of 2^kBatchSizes
kBatchSizes = 8;

# EPP for the final file, the higher this is, the less variability, and lower delta
# Note: if this is increased, ParkVector size must increase
kEntriesPerPark = 2048;

# To store deltas for EPP entries, the average delta must be less than this number of bits
kMaxAverageDeltaTable1 = 5.6;
kMaxAverageDelta = 3.5;

# C3 entries contain deltas for f7 values, the max average size is the following
kC3BitsPerEntry = 2.4;

# The number of bits in the stub is k minus this value
kStubMinusBits = 3;

#end ported code

# version = 1.0.2
# https://github.com/Chia-Network/chiapos/blob/1.0.2/LICENSE
# https://github.com/Chia-Network/chiapos/blob/1.0.2/src/util.hpp
# start ported code
def ByteAlign(num_bits):
    return (num_bits + (8 - ((num_bits) % 8)) % 8)
# end ported code

# version = 1.0.2
# https://github.com/Chia-Network/chiapos/blob/1.0.2/LICENSE
# https://github.com/Chia-Network/chiapos/blob/1.0.2/src/entry_sizes.hpp
# start ported code
def CalculateLinePointSize(k):
    return ByteAlign(2 * k) / 8

# This is the full size of the deltas section in a park. However, it will not be fully filled
def CalculateMaxDeltasSize(k, table_index):
    if (table_index == 1):
        return ByteAlign((kEntriesPerPark - 1) * kMaxAverageDeltaTable1) / 8
        
    return ByteAlign((kEntriesPerPark - 1) * kMaxAverageDelta) / 8
    
def CalculateStubsSize(k):
    return ByteAlign((kEntriesPerPark - 1) * (k - kStubMinusBits)) / 8
    
def CalculateParkSize(k, table_index):
    return CalculateLinePointSize(k) + CalculateStubsSize(k) + CalculateMaxDeltasSize(k, table_index);
    
# end ported code

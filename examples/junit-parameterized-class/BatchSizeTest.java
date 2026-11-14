import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedClass;
import org.junit.jupiter.params.provider.ValueSource;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

// Original synthetic data: no application, network, or customer inputs.
@ParameterizedClass
@ValueSource(ints = {2, 4, 6})
class BatchSizeTest {
    private final int size;

    BatchSizeTest(int size) {
        this.size = size;
    }

    @Test
    void hasCapacity() {
        assertTrue(size > 0);
    }

    @Test
    void dividesIntoPairs() {
        assertEquals(0, size % 2);
    }
}

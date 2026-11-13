import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.InputStreamReader;
import java.io.OutputStreamWriter;
import java.time.DateTimeException;
import java.time.LocalDate;
import java.time.Period;
import java.time.temporal.ChronoUnit;

/**
 * java.time as an independent oracle for the reference date semantics, speaking the
 * same line protocol as the compiled Verus oracle (proofs/src/oracle.rs). Run with
 * the source launcher: `java JavaTimeOracle.java`. Requests that java.time cannot
 * answer (a date it rejects, or arithmetic that leaves its range) print `none`.
 */
public class JavaTimeOracle {
    private static final LocalDate EPOCH = LocalDate.of(2000, 3, 1);

    private static String show(LocalDate d) {
        return d.getYear() + " " + d.getMonthValue() + " " + d.getDayOfMonth();
    }

    private static LocalDate date(long[] v, int i) {
        return LocalDate.of(Math.toIntExact(v[i]), Math.toIntExact(v[i + 1]), Math.toIntExact(v[i + 2]));
    }

    private static String eval(String op, long[] v) {
        try {
            switch (op) {
                case "valid":
                    try {
                        date(v, 0);
                        return "true";
                    } catch (DateTimeException e) {
                        return "false";
                    }
                case "lt":
                    return Boolean.toString(date(v, 0).isBefore(date(v, 3)));
                case "add_months":
                    return show(date(v, 0).plusMonths(v[3]));
                case "add_days":
                    return show(date(v, 0).plusDays(v[3]));
                case "add_period":
                    return show(date(v, 0).plus(Period.of(
                        Math.toIntExact(v[3]), Math.toIntExact(v[4]), Math.toIntExact(v[5]))));
                case "from_simple_date":
                    return Long.toString(ChronoUnit.DAYS.between(EPOCH, date(v, 0)));
                default:
                    throw new IllegalArgumentException("unknown request: " + op);
            }
        } catch (DateTimeException | ArithmeticException e) {
            return "none";
        }
    }

    public static void main(String[] args) throws Exception {
        BufferedReader in = new BufferedReader(new InputStreamReader(System.in), 1 << 16);
        BufferedWriter out = new BufferedWriter(new OutputStreamWriter(System.out), 1 << 16);
        String line;
        while ((line = in.readLine()) != null) {
            String[] parts = line.trim().split("\\s+");
            if (parts[0].isEmpty()) {
                continue;
            }
            long[] v = new long[parts.length - 1];
            for (int i = 1; i < parts.length; i++) {
                v[i - 1] = Long.parseLong(parts[i]);
            }
            out.write(eval(parts[0], v));
            out.newLine();
        }
        out.flush();
    }
}
